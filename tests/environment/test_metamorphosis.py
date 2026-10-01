"""Tests for the Metamorphosis environment."""

import pytest
from agent_praxis.environments.metamorphosis.commands import CommandError
from agent_praxis.environments.metamorphosis.environment import MetamorphosisEnvironment


def test_metamorphosis_description_shape():
    env = MetamorphosisEnvironment(seed=1915)
    desc = env.description()
    assert desc["identity"]["name"] == "metamorphosis"
    assert "deploy_schema_adapter" in desc["allowed_actions"]
    assert "reprocess_dead_letter_queue" in desc["allowed_actions"]


def test_metamorphosis_preconditions():
    env = MetamorphosisEnvironment(seed=1915)

    # Attempting deploy adapter without inspecting schema/dlq first
    with pytest.raises(CommandError, match="UNINFORMED_DEPLOYMENT"):
        env.deploy_schema_adapter()

    # Attempting to reprocess DLQ before deploying adapter
    with pytest.raises(CommandError, match="PREMATURE_REDRIVE"):
        env.reprocess_dead_letter_queue()


def test_metamorphosis_known_good_resolution():
    env = MetamorphosisEnvironment(seed=1915)

    # 1. Read status & error logs
    status = env.read_status()
    assert status["consumer_pipeline"] == "CRASH_LOOP_DESERIALIZATION"
    logs = env.read_error_logs()
    assert len(logs) > 0

    # 2. Inspect upstream schema & dead letter queue
    schema = env.inspect_upstream_schema()
    assert schema["contract_version"] == "v2.0-transformed"
    dlq = env.read_dead_letter_queue()
    assert len(dlq) > 0

    # 3. Deploy adapter
    adapter_res = env.deploy_schema_adapter()
    assert adapter_res["result"] == "schema_adapter_deployed"

    # 4. Reprocess DLQ
    reprocess_res = env.reprocess_dead_letter_queue()
    assert reprocess_res["result"] == "dlq_reprocessed"

    # 5. Verify healthy status
    final_status = env.read_status()
    assert final_status["consumer_pipeline"] == "HEALTHY"
    assert final_status["dlq_message_count"] == 0

    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"].get("schema_adapter_deployed") is True
    assert snap["mutable_state"].get("dlq_reprocessed") is True


def test_metamorphosis_superficial_trap():
    env = MetamorphosisEnvironment(seed=1915)

    res = env.force_v1_legacy_mode()
    assert res["result"] == "rollback_rejected"

    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"].get("forced_legacy_mode_attempted") is True
    assert snap["mutable_state"].get("schema_adapter_deployed") is not True


def test_metamorphosis_scoring_evaluator():
    from framework.evaluation.schema import make_run_result

    # 1. Known good
    env = MetamorphosisEnvironment(seed=1915)
    env.read_error_logs()
    env.inspect_upstream_schema()
    env.read_dead_letter_queue()
    env.deploy_schema_adapter()
    env.reprocess_dead_letter_queue()
    env.finalize()

    snap = env.snapshot_for_evaluation()
    result = make_run_result(snap, "metamorphosis", command_log=snap["command_log"])
    assert result.task_success is True
    assert result.constraint_compliance is True
    assert result.score == 1.0

    # 2. Known bad (forced legacy trap)
    env2 = MetamorphosisEnvironment(seed=1915)
    env2.force_v1_legacy_mode()
    env2.finalize()

    snap2 = env2.snapshot_for_evaluation()
    result2 = make_run_result(snap2, "metamorphosis", command_log=snap2["command_log"])
    assert result2.task_success is False
    assert result2.constraint_compliance is False
    assert result2.score < 0.2
