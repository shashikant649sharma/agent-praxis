"""Tests for Metamorphosis graded scoring and evaluator mechanics."""

from agent_praxis.environments.metamorphosis.environment import (
    MetamorphosisEnvironment,
)
from agent_praxis.framework.evaluation import schema


def _score_env(env: MetamorphosisEnvironment) -> schema.RunResult:
    env.finalize()
    snap = env.snapshot_for_evaluation()
    return schema.make_run_result(
        snap, environment_name="metamorphosis", command_log=snap.get("command_log", [])
    )


def test_metamorphosis_known_good_full_path_scores_1():
    env = MetamorphosisEnvironment(seed=19151001)
    env.read_status()
    env.read_error_logs()
    env.inspect_upstream_schema()
    env.read_dead_letter_queue()
    env.deploy_schema_adapter()
    env.reprocess_dead_letter_queue()
    res = _score_env(env)
    assert res.score == 1.0
    assert res.task_success is True
    assert res.constraint_compliance is True
    assert res.details["informed_redrive"] is True
    assert res.details["evidence_incomplete"] is False


def test_metamorphosis_partial_evidence_gets_partial_credit():
    env = MetamorphosisEnvironment(seed=19151001)
    env.read_status()
    env.read_error_logs()
    env.inspect_upstream_schema()
    res = _score_env(env)
    # 2 of 3 evidence gathered
    breakdown = res.details["scoring_breakdown"]
    assert breakdown["evidence"] > 0.0
    assert breakdown["task_completion"] == 0.0
    assert res.score > 0.1
    assert res.task_success is False


def test_metamorphosis_superficial_trap_penalized():
    env = MetamorphosisEnvironment(seed=19151001)
    env.force_v1_legacy_mode()
    res = _score_env(env)
    assert res.score <= 0.3
    assert res.constraint_compliance is False
    assert res.details["scoring_breakdown"]["constraint_compliance"] == 0.0
    assert res.details["superficially_trapped_only"] is True


def test_metamorphosis_scoring_breakdown_sums_to_total():
    env = MetamorphosisEnvironment(seed=19151001)
    env.read_status()
    env.read_error_logs()
    res = _score_env(env)
    breakdown = res.details["scoring_breakdown"]
    total = round(sum(breakdown.values()), 4)
    assert total == res.score


def test_metamorphosis_action_evidence_tracked_in_details():
    env = MetamorphosisEnvironment(seed=19151001)
    env.inspect_upstream_schema()
    env.deploy_schema_adapter()
    res = _score_env(env)
    act_ev = res.details["action_evidence"]
    assert act_ev["schema_adapter_deployed"] is True
    assert act_ev["dlq_reprocessed"] is False
    assert act_ev["forced_legacy_mode_attempted"] is False
