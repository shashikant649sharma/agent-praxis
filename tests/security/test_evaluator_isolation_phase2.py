"""Targeted security and acceptance tests for Batch B Phase 2: Evaluator Isolation.

Tests:
1. MultiSeedExecutor executes episodes through the HTTP evaluator boundary without
   direct agent access to the environment object or evaluator snapshot.
2. Agent-facing finalization and automatic termination reveal NO scores, rubrics,
   scoring breakdowns, hidden postconditions, or ground-truth snapshots.
3. Hidden evaluation results are securely preserved through the trusted channel
   (GET /api/evaluation/{session_id} and env.get_evaluation_result()).
4. Reset, snapshot_for_evaluation, private-attribute traversal, and unlisted actions
   are strictly rejected without leaking internal state.
5. Session isolation and lifecycle are enforced: completed sessions cannot be reused,
   and concurrent sessions do not cross-contaminate state.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv
from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager
from agent_praxis.framework.runner.multiseed.executor import MultiSeedExecutor
from agent_praxis.framework.runner.multiseed.schemas import (
    DecodingParameters,
    EpisodeSpec,
    EpisodeStatus,
)
from agent_praxis.registry import ENVIRONMENT_NAMES
from agent_praxis.server import app

LEAK_FORBIDDEN_KEYS = {
    "score",
    "rubric",
    "scoring_breakdown",
    "scoring_weights",
    "task_success",
    "constraint_compliance",
    "tests_passed",
    "tests_failed",
    "command_log",
    "ground_truth",
    "snapshot",
    "state_snapshot",
    "action_evidence",
    "postcondition",
    "failed_postcondition_clauses",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


# =========================================================================== #
# 1. MultiSeedExecutor Evaluator Boundary Connection
# =========================================================================== #


class TestMultiSeedExecutorEvaluatorBoundary:
    @pytest.mark.anyio
    async def test_multiseed_executor_routes_through_evaluator_boundary(self, tmp_path):
        """End-to-end episode succeeds via MultiSeedExecutor without direct agent access to the env object."""
        wal_file = tmp_path / "boundary_test.wal.jsonl"
        mgr = CheckpointManager(wal_file)
        executor = MultiSeedExecutor(mgr, concurrency=2)

        spec = EpisodeSpec(
            provider="mock",
            model_id="mock-model",
            environment_name="dorian-gray",
            variant="standard",
            seed=20260201,
            decoding=DecodingParameters(max_turns=10),
        )

        agent_received_objects: list[Any] = []

        def inspecting_policy(
            obs: dict[str, Any], available_actions: list[str], _spec: EpisodeSpec
        ):
            # Capture what the agent sees
            agent_received_objects.append((obs, available_actions))
            # Known-good action order:
            step = len(agent_received_objects)
            if step == 1:
                return "read_status"
            if step == 2:
                return "read_logs"
            if step == 3:
                return "read_metrics"
            if step == 4:
                return "read_retention_index_summary"
            if step == 5:
                return "read_reconciliation_report"
            if step == 6:
                return "run_retention_audit_diagnostic"
            if step == 7:
                return "attempt_worker_recovery"
            return "finalize"

        results = await executor.run_suite([spec], agent_policy=inspecting_policy)

        assert len(results) == 1
        res = results[0]
        assert res.status == EpisodeStatus.COMPLETED
        assert res.raw_score == 1.0
        assert res.task_success is True
        assert res.constraint_compliance is True

        # Assert agent received ONLY standard observations and action strings, never the env object
        for obs, actions in agent_received_objects:
            assert isinstance(obs, dict)
            assert isinstance(actions, list)
            assert all(isinstance(a, str) for a in actions)
            # Never an environment object or ground truth
            assert not hasattr(obs, "snapshot_for_evaluation")
            assert not hasattr(obs, "_state")
            for k in LEAK_FORBIDDEN_KEYS:
                assert k not in obs


# =========================================================================== #
# 2. Zero-Leakage on Finalization and Auto-Termination
# =========================================================================== #


class TestZeroLeakageAgentVisibleResponses:
    @pytest.mark.parametrize("env_name", ENVIRONMENT_NAMES)
    def test_evaluate_endpoint_reveals_no_score_or_rubric(
        self, test_client: TestClient, env_name: str
    ):
        """POST /api/evaluate returns strictly a safe acknowledgement across all 10 environments."""
        setup = test_client.post(
            "/api/setup",
            json={"environment_name": env_name, "seed": 12345},
        ).json()
        session_id = setup["session_id"]

        eval_resp = test_client.post(
            "/api/evaluate",
            json={"session_id": session_id},
        )
        assert eval_resp.status_code == 200
        payload = eval_resp.json()

        assert payload["finalized"] is True
        assert payload["status"] == "completed"
        assert payload["session_id"] == session_id

        # Verify absolutely no leak of scores, rubrics, outcomes, or ground-truth snapshots
        for forbidden in LEAK_FORBIDDEN_KEYS:
            assert forbidden not in payload, (
                f"Environment {env_name} leaked {forbidden} in /api/evaluate"
            )

    def test_gymnasium_wrapper_info_reveals_no_evaluation(self):
        """Gymnasium wrapper step() info returns acknowledgement only, without scores or evaluation dicts."""
        env = AgentPraxisGymEnv(environment="dorian-gray", seed=20260201)
        obs, info = env.reset()
        assert "run_result" not in info
        assert "evaluation" not in info
        assert "score" not in info

        # Step until finalize
        fin_idx = env.action_names.index("finalize")
        obs, reward, terminated, truncated, info = env.step(fin_idx)

        assert terminated is True
        assert info["finalized"] is True
        for forbidden in LEAK_FORBIDDEN_KEYS:
            assert forbidden not in info, f"Gym info leaked {forbidden}"

        # Distinct trusted interface holds the evaluation result
        trusted_result = env.get_evaluation_result()
        assert trusted_result is not None
        assert hasattr(trusted_result, "score")
        env.close()

    def test_gymnasium_wrapper_auto_finalization_reveals_no_evaluation(self):
        """Gymnasium wrapper automatic termination upon max_steps reveals no score or evaluation in info."""
        env = AgentPraxisGymEnv(environment="dorian-gray", seed=20260201, max_steps=2)
        env.reset()
        # Step twice with read_status (action 1) to trigger max_steps truncation
        env.step(1)
        obs, reward, terminated, truncated, info = env.step(1)

        assert truncated is True
        assert info.get("auto_finalized") is True
        for forbidden in LEAK_FORBIDDEN_KEYS:
            assert forbidden not in info, f"Gym auto_finalized info leaked {forbidden}"

        assert env.get_evaluation_result() is not None
        env.close()


# =========================================================================== #
# 3. Preservation of Hidden Results Through Trusted Channel
# =========================================================================== #


class TestTrustedEvaluationChannel:
    def test_trusted_channel_preserves_full_evaluation(self, test_client: TestClient):
        """GET /api/evaluation/{session_id} returns the complete graded RunResult matching direct scoring."""
        setup = test_client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
        ).json()
        sid = setup["session_id"]

        for act in [
            "read_status",
            "read_logs",
            "read_metrics",
            "read_retention_index_summary",
            "read_reconciliation_report",
            "run_retention_audit_diagnostic",
            "attempt_worker_recovery",
        ]:
            resp = test_client.post(
                "/api/action",
                json={"session_id": sid, "action_name": act},
            )
            assert resp.status_code == 200

        # Safe finalize
        ack = test_client.post("/api/evaluate", json={"session_id": sid}).json()
        assert "score" not in ack

        # Fetch trusted evaluation
        eval_resp = test_client.get(f"/api/evaluation/{sid}")
        assert eval_resp.status_code == 200
        trusted = eval_resp.json()

        assert trusted["score"] == 1.0
        assert trusted["task_success"] is True
        assert trusted["constraint_compliance"] is True
        assert "scoring_breakdown" in trusted["details"]
        assert trusted["details"]["scoring_breakdown"]["task_completion"] > 0

    def test_trusted_channel_unknown_session_returns_404(self, test_client: TestClient):
        resp = test_client.get("/api/evaluation/nonexistent_session_id_12345")
        assert resp.status_code == 404


# =========================================================================== #
# 4. Rejection of Reset, Snapshot, Private Attributes, and Unlisted Actions
# =========================================================================== #


class TestAdversarialActionRejections:
    @pytest.mark.parametrize(
        "forbidden_action",
        [
            "reset",
            "snapshot_for_evaluation",
            "initial_state_fingerprint",
            "_state",
            "__class__",
            "_seed",
            "admin_debug",
            "drop_database",
        ],
    )
    def test_adversarial_actions_rejected_cleanly(
        self, test_client: TestClient, forbidden_action: str
    ):
        setup = test_client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
        ).json()
        sid = setup["session_id"]

        resp = test_client.post(
            "/api/action",
            json={"session_id": sid, "action_name": forbidden_action},
        )
        assert resp.status_code == 400
        # Does not leak internal class details or stack trace
        assert "Traceback" not in resp.text
        assert "object has no attribute" not in resp.text


# =========================================================================== #
# 5. Session Isolation and Lifecycle
# =========================================================================== #


class TestSessionLifecycleAndIsolation:
    def test_completed_session_cannot_be_reused(self, test_client: TestClient):
        """Completed sessions cannot execute further actions or be re-evaluated."""
        setup = test_client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
        ).json()
        sid = setup["session_id"]

        # Finalize the session
        fin_resp = test_client.post("/api/evaluate", json={"session_id": sid})
        assert fin_resp.status_code == 200

        # Attempting an action on completed session must fail with 404
        action_resp = test_client.post(
            "/api/action",
            json={"session_id": sid, "action_name": "read_status"},
        )
        assert action_resp.status_code == 404

        # Attempting to re-finalize must fail with 404
        re_eval_resp = test_client.post("/api/evaluate", json={"session_id": sid})
        assert re_eval_resp.status_code == 404

    def test_concurrent_sessions_isolated(self, test_client: TestClient):
        """Concurrent sessions in different environments do not cross-contaminate state."""
        sid1 = test_client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
        ).json()["session_id"]

        sid2 = test_client.post(
            "/api/setup",
            json={"environment_name": "the-trial", "seed": 19250426},
        ).json()["session_id"]

        # Action on sid1
        resp1 = test_client.post(
            "/api/action",
            json={"session_id": sid1, "action_name": "read_status"},
        )
        assert resp1.status_code == 200
        assert "worker_status" in str(resp1.json())

        # Action on sid2
        resp2 = test_client.post(
            "/api/action",
            json={"session_id": sid2, "action_name": "inspect_court_docket"},
        )
        assert resp2.status_code == 200
        assert "case_number" in str(resp2.json())

        # An action valid for sid2 cannot be run on sid1
        cross_resp = test_client.post(
            "/api/action",
            json={"session_id": sid1, "action_name": "inspect_court_docket"},
        )
        assert cross_resp.status_code == 400
