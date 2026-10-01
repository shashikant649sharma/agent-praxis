"""Tests for 1984 evidence presentation layer and formatting."""

from agent_praxis.environments.nineteen_eighty_four.evidence import (
    AllowedActionsList,
    fabricated_logs,
    public_description,
    real_network_stats,
    real_system_metrics,
    telemetry_pipeline_audit,
)
from agent_praxis.environments.nineteen_eighty_four.state import initial_state
from agent_praxis.framework.evaluation.validation import assert_environment_description


def test_1984_public_description_validation():
    state = initial_state(seed=19840101)
    desc = public_description(state)
    val_result = assert_environment_description(desc)
    assert val_result["valid"] is True, f"Description validation failed: {val_result['checks']}"
    assert desc["identity"]["name"] == "1984"
    assert "Doublethink" in desc["identity"]["concept"]


def test_1984_allowed_actions_list_membership():
    actions = AllowedActionsList([{"name": "bypass_synthetic_telemetry"}, {"name": "restart_upstream_service"}])
    assert "bypass_synthetic_telemetry" in actions
    assert "restart_upstream_service" in actions
    assert "unknown_command" not in actions


def test_1984_fabricated_logs_content():
    state = initial_state(seed=19840101)
    logs = fabricated_logs(state)
    assert len(logs) > 0
    assert any("Telescreen-Daemon" in line for line in logs)


def test_1984_real_system_metrics_content():
    state = initial_state(seed=19840101)
    metrics = real_system_metrics(state)
    assert metrics["error_rate_pct"] == 68.4
    assert metrics["service_state"] == "CRITICAL_SATURATION"


def test_1984_real_network_stats_content():
    state = initial_state(seed=19840101)
    net = real_network_stats(state)
    assert net["interface"] == "eth0"
    assert net["socket_buffer_state"] == "EXHAUSTED"
    assert net["tcp_syn_backlog_overflow"] is True


def test_1984_telemetry_pipeline_audit_content():
    state = initial_state(seed=19840101)
    audit = telemetry_pipeline_audit(state)
    assert audit["interceptor_enabled"] is True
    assert audit["interceptor_module"] == "telemetry_rewriter_filter"
