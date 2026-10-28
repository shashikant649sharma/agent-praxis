"""Regression and acceptance tests for Batch A correctness issues.

Pins:
- ISSUE-01: Unknown environment IDs fail explicitly in make_run_result (no fallback to Dorian Gray).
- ISSUE-02: Finalization failures in /api/evaluate are not suppressed and return HTTP 400.
- ISSUE-03: Concurrent actions are serialized per session using session action locks.
- ISSUE-04: Boolean values are rejected where genuine integer action arguments are required.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from agent_praxis.errors import CommandError
from agent_praxis.framework.evaluation.schema import make_run_result
from agent_praxis.registry import ENVIRONMENT_NAMES
from agent_praxis.server import app


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


# =========================================================================
# ISSUE-01: Unknown environment falls back to Dorian Gray scoring
# =========================================================================


class TestIssue01UnknownEnvironmentScorerDispatch:
    def test_unknown_environment_raises_explicit_value_error(self) -> None:
        fake_snapshot = {"command_log": [], "mutable_state": {}}
        with pytest.raises(ValueError, match="Unknown environment 'unknown-env'"):
            make_run_result(fake_snapshot, environment_name="unknown-env")

    def test_misspelled_environment_raises_explicit_value_error(self) -> None:
        fake_snapshot = {"command_log": [], "mutable_state": {}}
        with pytest.raises(ValueError, match="Unknown environment 'dorian_gray_typo'"):
            make_run_result(fake_snapshot, environment_name="dorian_gray_typo")

    @pytest.mark.parametrize("env_name", ENVIRONMENT_NAMES)
    def test_all_registered_environments_dispatch_cleanly(self, env_name: str) -> None:
        fake_snapshot = {
            "command_log": [],
            "mutable_state": {},
            "status": "INITIALIZED",
            "public_status": {},
        }
        res = make_run_result(fake_snapshot, environment_name=env_name)
        assert res.environment == env_name
        assert res.task_success is False


# =========================================================================
# ISSUE-02: Finalization errors are suppressed in /api/evaluate
# =========================================================================


class TestIssue02FinalizationErrorsNotSuppressed:
    def test_finalize_exception_returns_http_400_not_silent_success(
        self, test_client: TestClient
    ) -> None:
        setup_resp = test_client.post("/api/setup", json={"environment_name": "dorian-gray"})
        assert setup_resp.status_code == 200
        sid = setup_resp.json()["session_id"]

        with patch(
            "agent_praxis.environments.dorian_gray.environment.DorianGrayEnvironment.finalize",
            side_effect=CommandError("Hardware failure during storage flush"),
        ):
            eval_resp = test_client.post("/api/evaluate", json={"session_id": sid})
            assert eval_resp.status_code == 400
            data = eval_resp.json()
            assert "Finalization failed: Hardware failure during storage flush" in data["detail"]
            assert "finalized" not in data or data.get("finalized") is not True


# =========================================================================
# ISSUE-03: Concurrent actions may race within one session
# =========================================================================


class TestIssue03ConcurrentSessionSerialization:
    def test_concurrent_actions_serialized_per_session(self) -> None:
        from agent_praxis.server import (
            ActionRequest,
            EvaluateRequest,
            SetupRequest,
            evaluate,
            execute_action,
            setup_environment,
        )

        setup = setup_environment(SetupRequest(environment_name="dorian-gray"))
        sid = setup["session_id"]

        # Concurrently execute 12 actions on the same session
        actions = ["read_status", "read_logs", "read_metrics", "read_status"] * 3

        def send_action(act: str) -> dict[str, Any]:
            return execute_action(ActionRequest(session_id=sid, action_name=act))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(send_action, actions))

        assert all("result" in r for r in results)

        # Finalize should cleanly see all executed actions without state corruption
        ack = evaluate(EvaluateRequest(session_id=sid))
        assert ack["finalized"] is True
        assert "command_log" not in ack

        # Trusted channel contains full evaluation details and command_log
        from agent_praxis.server import get_evaluation

        eval_res = get_evaluation(sid)
        cmd_log = eval_res.get("details", {}).get("command_log", [])
        # command_log contains: setup description (0) + 12 actions + finalize
        assert len(cmd_log) == 1 + len(actions) + 1


# =========================================================================
# ISSUE-04: Boolean values can pass integer parameter checks
# =========================================================================


class TestIssue04BooleanRejectedForIntegerParameters:
    def test_boolean_rejected_for_sophies_choice_bay_integer(self, test_client: TestClient) -> None:
        setup_resp = test_client.post("/api/setup", json={"environment_name": "sophies-choice"})
        assert setup_resp.status_code == 200
        sid = setup_resp.json()["session_id"]

        # Boolean True passed for integer parameter 'bay' must be rejected with 400
        resp_bool = test_client.post(
            "/api/action",
            json={
                "session_id": sid,
                "action_name": "inspect_asset_manifest",
                "kwargs": {"bay": True},
            },
        )
        assert resp_bool.status_code == 400
        assert "Invalid type for parameter 'bay'" in resp_bool.json()["detail"]

        # Valid integer must succeed
        resp_int = test_client.post(
            "/api/action",
            json={
                "session_id": sid,
                "action_name": "inspect_asset_manifest",
                "kwargs": {"bay": 1},
            },
        )
        assert resp_int.status_code == 200
        assert "bay_id" in resp_int.json()["result"]

    def test_boolean_rejected_for_sorcerers_days_integer(self, test_client: TestClient) -> None:
        setup_resp = test_client.post(
            "/api/setup", json={"environment_name": "sorcerers-apprentice"}
        )
        assert setup_resp.status_code == 200
        sid = setup_resp.json()["session_id"]

        # Boolean False passed for integer parameter 'days' must be rejected with 400
        resp_bool = test_client.post(
            "/api/action",
            json={
                "session_id": sid,
                "action_name": "cleanup_by_age",
                "kwargs": {"days": False},
            },
        )
        assert resp_bool.status_code == 400
        assert "Invalid type for parameter 'days'" in resp_bool.json()["detail"]
