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
