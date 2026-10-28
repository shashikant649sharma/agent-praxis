"""Regression test suite proving score floor integrity (Phase 1).

Guarantees across all 10 environments that:
1. An agent that takes zero actions (no-op) receives strictly 0.0000 score.
2. An agent that reads all available diagnostic information and halts (read-only)
   receives strictly 0.0000 score (zero task success, zero compliance, zero efficiency, zero evidence credit).
3. An agent that repeats harmless observational actions in a loop receives strictly 0.0000 score.
4. No-op and read-only policies receive zero task_success credit.
"""

from __future__ import annotations

import contextlib

import pytest

from agent_praxis.framework.evaluation.schema import make_run_result
from agent_praxis.registry import ENVIRONMENT_NAMES
from tools.policy_ladder_baseline import (
    READ_ONLY_ACTIONS,
    _create_env,
    run_noop_policy,
    run_read_only_policy,
)


@pytest.mark.parametrize("env_name", list(ENVIRONMENT_NAMES))
def test_noop_scores_strictly_zero(env_name: str) -> None:
    """Zero actions taken must score 0.0000."""
    result = run_noop_policy(env_name, seed=20261028)
    assert result["score"] == 0.0, f"{env_name} noop scored non-zero: {result['score']}"
    assert result["task_success"] is False
    breakdown = result["scoring_breakdown"]
    for dim, score in breakdown.items():
        assert score == 0.0, f"{env_name} earned {score} in dimension {dim} for no-op"


@pytest.mark.parametrize("env_name", list(ENVIRONMENT_NAMES))
def test_read_only_investigator_scores_strictly_zero(env_name: str) -> None:
    """Reading all observational logs without attempting remediation must score 0.0000."""
    result = run_read_only_policy(env_name, seed=20261028)
    assert result["score"] == 0.0, f"{env_name} read-only scored non-zero: {result['score']}"
    assert result["task_success"] is False
    breakdown = result["scoring_breakdown"]
    for dim, score in breakdown.items():
        assert score == 0.0, f"{env_name} earned {score} in dimension {dim} for read-only"


@pytest.mark.parametrize("env_name", list(ENVIRONMENT_NAMES))
def test_repeated_harmless_reads_scores_strictly_zero(env_name: str) -> None:
    """Calling harmless read actions repeatedly without task attempt must score 0.0000."""
    env = _create_env(env_name, seed=20261028)
    actions = READ_ONLY_ACTIONS.get(env_name, ["read_status"])
    read_cmd = actions[0] if actions else "read_status"
    method = getattr(env, read_cmd, None)
    if method is not None:
        for _ in range(5):
            with contextlib.suppress(Exception):
                method()
    with contextlib.suppress(Exception):
        env.finalize()
    snap = env.snapshot_for_evaluation()
    res = make_run_result(snap, environment_name=env_name, command_log=snap.get("command_log", []))
    assert res.score == 0.0, f"{env_name} harmless repeat scored {res.score}"
    assert res.task_success is False
