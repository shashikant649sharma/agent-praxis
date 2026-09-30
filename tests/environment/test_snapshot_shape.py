"""Tests for snapshot shape validation in the Dorian Gray environment."""

import agent_praxis.environments.dorian_gray.environment as env_mod

_REQUIRED_SNAPSHOT_KEYS = [
    "seed",
    "started_at",
    "degraded_since",
    "ground_truth",
    "public_status",
    "evidence",
    "mutable_state",
    "command_log",
]

_REQUIRED_GROUND_TRUTH_KEYS = [
    "worker_state",
    "root_cause",
    "affected_store",
    "queue_name",
    "last_successful_job_at",
    "jobs_lost_or_unprocessed",
    "reconciliation_coverage_pct",
    "healthcheck_gate",
    "note",
]

_FORBIDDEN_SNAPSHOT_KEYS = ["final_state", "evaluator_note"]


def test_snapshot_has_required_keys():
    """snapshot_for_evaluation() after finalize returns a dict with required keys."""
    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.finalize()
    snap = env.snapshot_for_evaluation()

    for key in _REQUIRED_SNAPSHOT_KEYS:
        assert key in snap, f"Snapshot missing required key: {key!r}"


def test_snapshot_ground_truth_has_required_keys():
    """ground_truth is a dict with the expected keys."""
    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.finalize()
    snap = env.snapshot_for_evaluation()
    gt = snap["ground_truth"]

    assert isinstance(gt, dict), "ground_truth must be a dict"
    for key in _REQUIRED_GROUND_TRUTH_KEYS:
        assert key in gt, f"ground_truth missing required key: {key!r}"


def test_snapshot_ground_truth_worker_state_is_degraded():
    """ground_truth.worker_state is 'degraded'."""
    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["ground_truth"]["worker_state"] == "degraded"


def test_snapshot_command_log_is_list():
    """command_log is a list."""
    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert isinstance(snap["command_log"], list), "command_log must be a list"


def test_snapshot_does_not_leak_evaluator_keys():
    """Snapshot does NOT contain final_state or evaluator_note (no leaks)."""
    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.finalize()
    snap = env.snapshot_for_evaluation()

    for key in _FORBIDDEN_SNAPSHOT_KEYS:
        assert key not in snap, f"Snapshot must not contain forbidden key: {key!r}"
