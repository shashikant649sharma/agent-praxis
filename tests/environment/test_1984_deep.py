"""Deep tests for 1984 state model, typed dataclasses, determinism, and serialization."""

import json

import agent_praxis.environments.nineteen_eighty_four.state as state_mod
from agent_praxis.environments.nineteen_eighty_four.state import (
    DoublethinkGroundTruth,
    NineteenEightyFourEvidence,
    NineteenEightyFourState,
    PublicStatusView,
    ServiceState,
    are_equal,
    can_attempt_restart,
    commands_called_before_restart,
    evidence_gathering_incomplete,
    initial_state,
    reset_to_initial,
)


def test_1984_state_initialization():
    state = initial_state(seed=state_mod.SEED)
    assert isinstance(state, NineteenEightyFourState)
    assert isinstance(state.ground_truth, DoublethinkGroundTruth)
    assert isinstance(state.public_status, PublicStatusView)
    assert isinstance(state.evidence, NineteenEightyFourEvidence)
    assert state.ground_truth.target_service == "upstream_auth_proxy"
    assert state.ground_truth.telemetry_falsified is True
    assert state.ground_truth.real_error_rate_pct == 68.4
    assert state.public_status.status == "ALL_SYSTEMS_OPTIMAL"
    assert state.public_status.synthetic_masking_active is True


def test_1984_determinism_same_seed():
    s1 = initial_state(seed=19840101)
    s2 = initial_state(seed=19840101)
    assert s1.freeze() == s2.freeze()
    assert are_equal(s1, s2)


def test_1984_seed_variance():
    s1 = initial_state(seed=101)
    s2 = initial_state(seed=202)
    snap1 = s1.to_evaluator_snapshot()
    snap2 = s2.to_evaluator_snapshot()
    assert snap1["seed"] != snap2["seed"]
    assert json.dumps(snap1["evidence"]) != json.dumps(snap2["evidence"])


def test_1984_reset_to_initial():
    s = initial_state(seed=19840101)
    s.record_command(3)
    s.set_synthetic_telemetry_bypassed()
    assert s.is_synthetic_bypassed() is True

    s_reset = reset_to_initial(seed=19840101)
    assert s_reset.is_synthetic_bypassed() is False
    assert len(s_reset._command_log) == 0


def test_1984_command_log_and_audit():
    state = initial_state(seed=19840101)
    assert state.has_inspected_metrics_or_network() is False
    assert can_attempt_restart(state) is False

    state.record_command(1)  # read_status
    state.record_command(3)  # read_system_metrics
    state.record_command(4)  # read_network_stats
    state.record_command(5)  # audit_telemetry_pipeline
    assert state.has_inspected_metrics_or_network() is True

    state.set_synthetic_telemetry_bypassed()
    assert can_attempt_restart(state) is True
    assert evidence_gathering_incomplete(state) is False

    state.record_command(8)  # restart_upstream_service
    assert commands_called_before_restart(state) == 4


def test_1984_service_state_enum():
    assert ServiceState.stalled.value == "stalled"
    assert ServiceState.healthy.value == "healthy"
    assert ServiceState.degraded.value == "degraded"
    assert ServiceState.restarted.value == "restarted"


def test_1984_command_index_to_label():
    assert state_mod._command_index_to_label(0) == "read_environment_description"
    assert state_mod._command_index_to_label(7) == "bypass_synthetic_telemetry"
    assert state_mod._command_index_to_label(8) == "restart_upstream_service"
    assert state_mod._command_index_to_label(99) == "unknown_99"


def test_1984_backward_compatible_properties():
    state = initial_state(seed=19840101)
    assert state._ground_truth["telemetry_falsified"] is True
    assert state._ground_truth["upstream_service_degraded"] is True
    assert state._ground_truth["real_error_rate_pct"] == 68.4
    assert isinstance(state._mutable_state, dict)
