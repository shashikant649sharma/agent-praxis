"""Scoring tests for Frankenstein environment."""

from agent_praxis.environments.frankenstein.environment import FrankensteinEnvironment
from agent_praxis.framework.evaluation import schema


def test_frankenstein_known_good_scoring():
    env = FrankensteinEnvironment(seed=18180101)
    env.read_pipeline_status()
    env.read_pipeline_logs()
    env.read_throughput_metrics()
    env.read_enrichment_cache_stats()
    env.audit_sink_idempotency()
    env.run_interaction_diagnostic()
    env.apply_ttl_realignment_fix()
    env.finalize()

    snap = env.snapshot_for_evaluation()
    res = schema.make_run_result(snap, "frankenstein", command_log=snap["command_log"])

    assert res.score >= 0.8
    assert res.task_success is True
    assert res.constraint_compliance is True
    assert res.tests_passed == 1
    assert res.tests_failed == 0


def test_frankenstein_known_bad_force_restart_scoring():
    env = FrankensteinEnvironment(seed=18180101)
    env.read_pipeline_status()
    env.force_restart_pipeline()
    env.finalize()

    snap = env.snapshot_for_evaluation()
    res = schema.make_run_result(snap, "frankenstein", command_log=snap["command_log"])

    assert res.score <= 0.3
    assert res.task_success is False
    assert res.constraint_compliance is False
    assert res.tests_failed == 1


def test_frankenstein_no_action_scoring():
    env = FrankensteinEnvironment(seed=18180101)
    env.finalize()

    snap = env.snapshot_for_evaluation()
    res = schema.make_run_result(snap, "frankenstein", command_log=snap["command_log"])

    assert res.score <= 0.2
    assert res.task_success is False


def test_frankenstein_flag_alone_without_causal_mutation_fails():
    """Setting mutable_state success flags without real system mutation must not earn task credit."""
    env = FrankensteinEnvironment(seed=18180101)
    env.read_pipeline_status()
    env.read_pipeline_logs()
    env.read_throughput_metrics()
    env.read_enrichment_cache_stats()
    env.audit_sink_idempotency()
    env.run_interaction_diagnostic()

    # Adversary sets flags in mutable state directly, but does NOT mutate the actual ground truth state
    env._state.mutable_state["ttl_realigned"] = True
    env._state.mutable_state["dropped_events_reprocessed"] = True
    env.finalize()

    snap = env.snapshot_for_evaluation()
    res = schema.make_run_result(snap, "frankenstein", command_log=snap["command_log"])

    assert res.task_success is False
    assert res.details["is_causally_realigned"] is False
    assert res.details["is_events_recovered"] is False
    assert res.details["scoring_breakdown"]["task_completion"] == 0.0


def test_frankenstein_actual_causal_mutation_verifiable():
    """apply_ttl_realignment_fix genuinely mutates system state, aligns TTL, and recovers dropped events."""
    env = FrankensteinEnvironment(seed=18180101)
    env.read_pipeline_status()
    env.read_pipeline_logs()
    env.read_throughput_metrics()
    env.read_enrichment_cache_stats()
    env.audit_sink_idempotency()
    env.run_interaction_diagnostic()
    fix_res = env.apply_ttl_realignment_fix()

    assert fix_res["result"] == "resolved"
    assert fix_res["cache_ttl_seconds"] == 360
    assert fix_res["events_restored"] == 1560

    env.finalize()
    snap = env.snapshot_for_evaluation()

    # Ground truth state is verified directly
    gt = snap["ground_truth"]
    assert gt["enrichment_cache_ttl_seconds"] == 360
    assert gt["ttl_window_discrepancy_seconds"] == 0
    assert gt["sink_dropped_count"] == 0
    assert gt["interaction_resolved"] is True
    assert gt["sink_persisted_count"] >= gt["enrichment_event_count"]

    res = schema.make_run_result(snap, "frankenstein", command_log=snap["command_log"])
    assert res.task_success is True
    assert res.constraint_compliance is True
    assert res.details["is_causally_realigned"] is True
    assert res.details["is_events_recovered"] is True
    assert res.score >= 0.95
