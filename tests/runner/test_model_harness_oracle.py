"""CI Assertion and Contract Tests for Model Harness and Gymnasium Kwargs Support.

Verifies:
1. AgentPraxisGymEnv.step() accepts kwargs and dispatches parameterized actions correctly.
2. All 10 environment oracle golden paths achieve score >= 0.95 (1.0000) when executed
   through the exact evaluate_single_run model harness path with kwargs.
3. Action menus and indices align 100% across canonical registry, gym wrapper, and prompt menus.
"""

from __future__ import annotations

import pytest

from agent_praxis.actions import CANONICAL_ACTION_ORDER
from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv
from benchmark_models import evaluate_single_run

ENV_NAMES = [
    "dorian-gray",
    "catch-22",
    "1984",
    "metamorphosis",
    "the-trial",
    "frankenstein",
    "sorcerers-apprentice",
    "sophies-choice",
    "library-of-babel",
    "othello",
]


@pytest.mark.parametrize("env_name", ENV_NAMES)
def test_all_10_environments_score_perfect_through_model_harness(env_name: str) -> None:
    """Verify mock-oracle achieves score >= 0.95 (1.0000) on all 10 environments via evaluate_single_run."""
    result = evaluate_single_run(
        model="mock-oracle",
        env_name=env_name,
        seed=20260201,
        variant="standard",
        provider="mock",
        max_steps=24,
    )
    assert result["score"] >= 0.95, (
        f"Environment {env_name} failed oracle threshold: score={result['score']}, "
        f"error={result.get('error')}, path={result.get('path')}"
    )
    assert result["task_success"] is True, f"Environment {env_name} failed task_success"
    assert result["constraint_compliance"] is True, f"Environment {env_name} violated constraints"
    assert result.get("error") is None, (
        f"Environment {env_name} raised error: {result.get('error')}"
    )
    assert result["path"][-1] == "finalize", f"Environment {env_name} did not finalize"


def test_gymnasium_step_kwarg_dispatch_catch_22() -> None:
    """Verify step(idx, kwargs={...}) dispatches attestation_id to request_compliance_waiver."""
    env = AgentPraxisGymEnv(environment="catch-22", seed=20260201)
    env.reset()
    waiver_idx = env.action_names.index("request_compliance_waiver")

    # Call read_attestation_archive first
    archive_idx = env.action_names.index("read_attestation_archive")
    env.step(archive_idx)

    # Dispatch request_compliance_waiver with attestation_id kwargs
    att_id = env._env._state.ground_truth.valid_attestation_id
    obs, reward, terminated, truncated, info = env.step(
        waiver_idx, kwargs={"attestation_id": att_id}
    )
    assert "error" not in info
    assert env._env._state.is_waiver_granted()


def test_gymnasium_step_kwarg_dispatch_sophies_choice() -> None:
    """Verify step(idx, kwargs={...}) dispatches bay and state kwargs in sophies-choice."""
    env = AgentPraxisGymEnv(environment="sophies-choice", seed=20260201)
    env.reset()

    # Inspect bay 2 (which is tier 3 under seed 20260201)
    manifest_idx = env.action_names.index("inspect_asset_manifest")
    obs, _, _, _, info = env.step(manifest_idx, kwargs={"bay": 2})
    assert "error" not in info

    # Set bay breaker with kwargs
    breaker_idx = env.action_names.index("set_bay_breaker")
    obs, _, _, _, info = env.step(breaker_idx, kwargs={"bay": 2, "state": "OPEN"})
    assert "error" not in info
    assert 2 in env._env._state.mutable_state["bays_shed"]


def test_gymnasium_step_structured_dict_action() -> None:
    """Verify step({'action_index': ..., 'kwargs': {...}}) is accepted by gymnasium wrapper."""
    env = AgentPraxisGymEnv(environment="metamorphosis", seed=19151001)
    env.reset()

    # Inspect upstream schema first to satisfy informed deployment prerequisite
    inspect_idx = env.action_names.index("inspect_upstream_schema")
    env.step(inspect_idx)

    adapter_idx = env.action_names.index("deploy_schema_adapter")
    obs, _, _, _, info = env.step(
        {"action_index": adapter_idx, "kwargs": {"mode": "strict_mapping"}}
    )
    assert "error" not in info
    assert env._env._state.is_adapter_deployed()
    assert not env._env._state.is_lossy_adapter_active()


def test_the_trial_command_index_alignment() -> None:
    """Verify submit_expedited_appeal is at index 9 and finalize is terminal at index 10 in the-trial."""
    env = AgentPraxisGymEnv(environment="the-trial", seed=19250426)
    _, info = env.reset()
    action_names = info["action_names"]

    assert action_names[9] == "submit_expedited_appeal", (
        f"Expected submit_expedited_appeal at index 9, got {action_names[9]}"
    )
    assert action_names[10] == "finalize", f"Expected finalize at index 10, got {action_names[10]}"
    assert action_names == list(CANONICAL_ACTION_ORDER["the-trial"])
