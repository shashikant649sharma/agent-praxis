"""Deep tests for Metamorphosis state model, typed dataclasses, determinism, and serialization."""

import json

import agent_praxis.environments.metamorphosis.state as state_mod
from agent_praxis.environments.metamorphosis.state import (
    MetamorphosisEvidence,
    MetamorphosisState,
    PipelineStatus,
    PublicStatusView,
    SchemaMutationGroundTruth,
    are_equal,
    can_attempt_redrive,
    commands_called_before_redrive,
    evidence_gathering_incomplete,
    initial_state,
    reset_to_initial,
)


def test_metamorphosis_state_initialization():
    state = initial_state(seed=state_mod.SEED)
    assert isinstance(state, MetamorphosisState)
    assert isinstance(state.ground_truth, SchemaMutationGroundTruth)
    assert isinstance(state.public_status, PublicStatusView)
    assert isinstance(state.evidence, MetamorphosisEvidence)
    assert state.ground_truth.upstream_service_name == "Gregor Microservice"
    assert state.ground_truth.upstream_transformed is True
    assert state.ground_truth.dlq_message_count == 18420
    assert state.public_status.consumer_pipeline == "CRASH_LOOP_DESERIALIZATION"
    assert state.public_status.schema_adapter == "NONE"


def test_metamorphosis_determinism_same_seed():
    s1 = initial_state(seed=19151001)
    s2 = initial_state(seed=19151001)
    assert s1.freeze() == s2.freeze()
    assert are_equal(s1, s2)


def test_metamorphosis_seed_variance():
    s1 = initial_state(seed=101)
    s2 = initial_state(seed=202)
    snap1 = s1.to_evaluator_snapshot()
    snap2 = s2.to_evaluator_snapshot()
    assert snap1["seed"] != snap2["seed"]
    assert json.dumps(snap1["evidence"]) != json.dumps(snap2["evidence"])


def test_metamorphosis_reset_to_initial():
    s = initial_state(seed=19151001)
    s.record_command(3)
    s.set_schema_adapter_deployed()
    assert s.is_adapter_deployed() is True

    s_reset = reset_to_initial(seed=19151001)
    assert s_reset.is_adapter_deployed() is False
    assert len(s_reset._command_log) == 0


def test_metamorphosis_command_log_and_audit():
    state = initial_state(seed=19151001)
    assert state.has_inspected_schema_or_dlq() is False
    assert can_attempt_redrive(state) is False

    state.record_command(1)  # read_status
    state.record_command(2)  # read_error_logs
    state.record_command(3)  # inspect_upstream_schema
    state.record_command(4)  # read_dead_letter_queue
    assert state.has_inspected_schema_or_dlq() is True

    state.set_schema_adapter_deployed()
    assert can_attempt_redrive(state) is True
    assert evidence_gathering_incomplete(state) is False

    state.record_command(7)  # reprocess_dead_letter_queue
    assert commands_called_before_redrive(state) == 4


def test_metamorphosis_pipeline_status_enum():
    assert PipelineStatus.crash_loop.value == "crash_loop"
    assert PipelineStatus.adapter_deployed.value == "adapter_deployed"
    assert PipelineStatus.reprocessed.value == "reprocessed"
    assert PipelineStatus.healthy.value == "healthy"


def test_metamorphosis_command_index_to_label():
    assert state_mod._command_index_to_label(0) == "read_environment_description"
    assert state_mod._command_index_to_label(6) == "deploy_schema_adapter"
    assert state_mod._command_index_to_label(7) == "reprocess_dead_letter_queue"
    assert state_mod._command_index_to_label(99) == "unknown_99"


def test_metamorphosis_backward_compatible_properties():
    state = initial_state(seed=19151001)
    assert state._ground_truth["upstream_transformed"] is True
    assert state._ground_truth["pipeline_crashed"] is True
    assert state._ground_truth["dlq_message_count"] == 18420
    assert isinstance(state._mutable_state, dict)
