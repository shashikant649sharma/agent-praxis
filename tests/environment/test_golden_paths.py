"""Regression tests to ensure all 10 environment golden paths are fully reachable.

Tests all 10 environments across both standard and control variants (20 tests),
guaranteeing that scripted oracle trajectories remain in sync with environment
signatures and score >= 0.95 with task_success=True and constraint_compliance=True.
"""

from __future__ import annotations

import pytest

from run_10_environments_benchmark import ALL_ENVIRONMENTS, run_golden_path


@pytest.mark.parametrize("env_id", [e["id"] for e in ALL_ENVIRONMENTS])
@pytest.mark.parametrize("variant", ["standard", "control"])
def test_golden_path_is_reachable(env_id: str, variant: str) -> None:
    result = run_golden_path(env_id, variant=variant)
    assert result.task_success is True, f"{env_id}/{variant} failed task_success"
    assert result.constraint_compliance is True, f"{env_id}/{variant} failed constraint_compliance"
    assert result.score >= 0.95, f"{env_id}/{variant} scored {result.score}"
