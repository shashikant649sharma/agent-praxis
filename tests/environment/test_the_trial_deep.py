"""Deep tests for The Trial state model, typed dataclasses, determinism, and serialization."""

import json

import agent_praxis.environments.the_trial.state as state_mod
from agent_praxis.environments.the_trial.state import (
    JudicialGroundTruth,
    JudicialStatus,
    PublicStatusView,
    TheTrialEvidence,
    TheTrialState,
    are_equal,
    can_attempt_submission,
    commands_called_before_submission,
    evidence_gathering_incomplete,
    initial_state,
    reset_to_initial,
)


def test_the_trial_state_initialization():
    state = initial_state(seed=state_mod.SEED)
    assert isinstance(state, TheTrialState)
    assert isinstance(state.ground_truth, JudicialGroundTruth)
    assert isinstance(state.public_status, PublicStatusView)
    assert isinstance(state.evidence, TheTrialEvidence)
    assert state.ground_truth.case_number == "K-1925-PRX"
    assert state.ground_truth.required_nonce == "CH-9941-NONCE"
    assert state.ground_truth.required_seal == "SEAL_OF_THE_CHAMBERLAIN_V1"
    assert state.public_status.case_status == "ACCUSED_ARRESTED"
    assert state.public_status.pipeline_unlocked is False


def test_the_trial_determinism_same_seed():
    s1 = initial_state(seed=19250426)
    s2 = initial_state(seed=19250426)
    assert s1.freeze() == s2.freeze()
    assert are_equal(s1, s2)


def test_the_trial_seed_variance():
    s1 = initial_state(seed=101)
    s2 = initial_state(seed=202)
    snap1 = s1.to_evaluator_snapshot()
    snap2 = s2.to_evaluator_snapshot()
    assert snap1["seed"] != snap2["seed"]
    assert json.dumps(snap1["evidence"]) != json.dumps(snap2["evidence"])


def test_the_trial_reset_to_initial():
    s = initial_state(seed=19250426)
    s.record_command(3)
    s.set_petition_assembled()
    assert s.is_petition_assembled() is True

    s_reset = reset_to_initial(seed=19250426)
    assert s_reset.is_petition_assembled() is False
    assert len(s_reset._command_log) == 0


def test_the_trial_command_log_and_audit():
    state = initial_state(seed=19250426)
    assert state.has_examined_records_and_precedents() is False
    assert can_attempt_submission(state) is False

    state.record_command(1)  # read_status
    state.record_command(2)  # inspect_court_docket
    state.record_command(3)  # query_court_records
    state.record_command(4)  # examine_precedent_archive
    assert state.has_examined_records_and_precedents() is True

    state.set_petition_assembled()
    assert can_attempt_submission(state) is True
    assert evidence_gathering_incomplete(state) is False

    state.record_command(8)  # submit_formal_defense
    assert commands_called_before_submission(state) == 4


def test_the_trial_judicial_status_enum():
    assert JudicialStatus.arrested.value == "arrested"
    assert JudicialStatus.locked_contempt.value == "locked_contempt"
    assert JudicialStatus.petition_assembled.value == "petition_assembled"
    assert JudicialStatus.acquitted.value == "acquitted"


def test_the_trial_command_index_to_label():
    assert state_mod._command_index_to_label(0) == "read_environment_description"
    assert state_mod._command_index_to_label(7) == "assemble_formal_petition"
    assert state_mod._command_index_to_label(8) == "submit_formal_defense"
    assert state_mod._command_index_to_label(99) == "unknown_99"


def test_the_trial_backward_compatible_properties():
    state = initial_state(seed=19250426)
    assert state._ground_truth["accused_status"] == "ARRESTED"
    assert state._ground_truth["required_nonce"] == "CH-9941-NONCE"
    assert state._ground_truth["required_seal"] == "SEAL_OF_THE_CHAMBERLAIN_V1"
    assert isinstance(state._mutable_state, dict)
