"""Scoring tests for Frankenstein environment."""

import dataclasses

import pytest

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
    """apply_ttl_realignment_fix genuinely mutates operational state while keeping ground truth immutable."""
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

    # Evaluator independence: initial ground truth remains completely unchanged
    gt = snap["ground_truth"]
    assert gt["enrichment_cache_ttl_seconds"] == 300
    assert gt["ttl_window_discrepancy_seconds"] == 60
    assert gt["sink_dropped_count"] == 1560

    # Operational system state is verified directly
    op = snap["operational_state"]
    assert op["configured_enrichment_cache_ttl_seconds"] == 360
    assert op["active_ttl_window_discrepancy_seconds"] == 0
    assert op["sink_dropped_count"] == 0
    assert op["interaction_resolved"] is True
    assert op["sink_persisted_count"] >= gt["enrichment_event_count"]

    res = schema.make_run_result(snap, "frankenstein", command_log=snap["command_log"])
    assert res.task_success is True
    assert res.constraint_compliance is True
    assert res.details["is_causally_realigned"] is True
    assert res.details["is_events_recovered"] is True
    assert res.score >= 0.95


def test_frankenstein_ground_truth_immutable_under_recovery():
    """Regression test proving recovery leaves the initial ground-truth record unchanged and frozen."""
    env = FrankensteinEnvironment(seed=18180101)
    gt_before = env._state.ground_truth.to_dict()

    # Step through diagnostics and apply fix
    env.read_pipeline_status()
    env.read_pipeline_logs()
    env.read_throughput_metrics()
    env.read_enrichment_cache_stats()
    env.audit_sink_idempotency()
    env.run_interaction_diagnostic()
    env.apply_ttl_realignment_fix()

    # Ground truth object and its fields must be identical before and after
    gt_after = env._state.ground_truth.to_dict()
    assert gt_before == gt_after

    # Ground truth is a frozen dataclass; direct mutation attempts must raise FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        env._state.ground_truth.enrichment_cache_ttl_seconds = 360  # type: ignore[misc]

    # Operational state, by contrast, is updated
    assert env._state.operational_state.configured_enrichment_cache_ttl_seconds == 360
    assert env._state.operational_state.interaction_resolved is True


def test_frankenstein_evidence_consistency_post_remediation():
    """Post-remediation evidence deliberately preserves historical logs while updating live metrics."""
    env = FrankensteinEnvironment(seed=18180101)
    env.read_pipeline_status()
    env.read_pipeline_logs()
    env.read_throughput_metrics()
    env.read_enrichment_cache_stats()
    env.audit_sink_idempotency()
    env.run_interaction_diagnostic()
    env.apply_ttl_realignment_fix()

    # Historical logs preserve their pre-remediation timestamps
    logs = env.read_pipeline_logs()
    historical_logs = [log for log in logs if log["service"] in ("ingress", "enrichment", "sink")]
    assert len(historical_logs) >= 3
    # A new remediation event is appended
    remediation_logs = [log for log in logs if log["service"] == "pipeline-remediation"]
    assert len(remediation_logs) == 1
    assert "Cache TTL realigned" in remediation_logs[0]["message"]

    # Live telemetry and audit reflect recovered state
    metrics = env.read_throughput_metrics()
    assert metrics["sink_dropped_count"] == 0
    assert metrics["pipeline_loss_ratio"] == 0.0

    audit = env.audit_sink_idempotency()
    assert audit["duplicates_rejected"] == 0
    assert audit["post_recovery_audit"]["status"] == "RECOVERED"
