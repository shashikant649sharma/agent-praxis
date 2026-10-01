"""Deep tests for Catch-22 state model, typed dataclasses, determinism, and serialization."""

import json

import agent_praxis.environments.catch_22.state as state_mod
from agent_praxis.environments.catch_22.state import (
    Catch22Evidence,
    Catch22State,
    ContradictionGroundTruth,
    DatasetStatus,
    PublicStatusView,
    are_equal,
    can_attempt_release,
    commands_called_before_release,
    evidence_gathering_incomplete,
    initial_state,
    reset_to_initial,
)


def test_catch22_state_initialization():
    state = initial_state(seed=state_mod.SEED)
    assert isinstance(state, Catch22State)
    assert isinstance(state.ground_truth, ContradictionGroundTruth)
    assert isinstance(state.public_status, PublicStatusView)
    assert isinstance(state.evidence, Catch22Evidence)
    assert state.ground_truth.dataset_id == "DS-99"
    assert state.ground_truth.circular_dependency is True
    assert state.ground_truth.valid_attestation_id == "ATT-2026-0114"
    assert state.public_status.status == "QUARANTINED"
    assert "COMPLIANCE_HOLD" in state.public_status.active_locks


def test_catch22_determinism_same_seed():
    s1 = initial_state(seed=20260301)
    s2 = initial_state(seed=20260301)
    assert s1.freeze() == s2.freeze()
    assert are_equal(s1, s2)


def test_catch22_seed_variance():
    s1 = initial_state(seed=101)
    s2 = initial_state(seed=202)
    # Different seeds should yield different evidence randomness
    snap1 = s1.to_evaluator_snapshot()
    snap2 = s2.to_evaluator_snapshot()
    assert snap1["seed"] != snap2["seed"]
    assert json.dumps(snap1["evidence"]) != json.dumps(snap2["evidence"])


def test_catch22_reset_to_initial():
    s = initial_state(seed=20260301)
    s.record_command(2)
    s.set_waiver_granted()
    assert s.is_waiver_granted() is True

    s_reset = reset_to_initial(seed=20260301)
    assert s_reset.is_waiver_granted() is False
    assert len(s_reset._command_log) == 0


def test_catch22_command_log_and_audit():
    state = initial_state(seed=20260301)
    assert state.has_read_archive() is False
    assert can_attempt_release(state) is False

    state.record_command(1)  # read_status
    state.record_command(2)  # read_policy_rules
    state.record_command(3)  # read_dataset_metadata
    state.record_command(4)  # read_attestation_archive
    assert state.has_read_archive() is True

    state.set_waiver_granted()
    assert can_attempt_release(state) is True
    assert evidence_gathering_incomplete(state) is False

    state.record_command(8)  # release_dataset
    assert commands_called_before_release(state) == 4


def test_catch22_dataset_status_enum():
    assert DatasetStatus.quarantined.value == "quarantined"
    assert DatasetStatus.waiver_pending.value == "waiver_pending"
    assert DatasetStatus.released.value == "released"


def test_catch22_command_index_to_label():
    assert state_mod._command_index_to_label(0) == "read_environment_description"
    assert state_mod._command_index_to_label(8) == "release_dataset"
    assert state_mod._command_index_to_label(99) == "unknown_99"


def test_catch22_backward_compatible_properties():
    state = initial_state(seed=20260301)
    assert state._ground_truth["dataset_state"] == "quarantined"
    assert state._ground_truth["circular_dependency"] is True
    assert state._ground_truth["valid_attestation_exists"] == "ATT-2026-0114"
    assert isinstance(state._mutable_state, dict)
