"""Tests for the 1984 environment."""

import pytest
from agent_praxis.environments.nineteen_eighty_four.commands import CommandError
from agent_praxis.environments.nineteen_eighty_four.environment import NineteenEightyFourEnvironment


def test_1984_description_shape():
    env = NineteenEightyFourEnvironment(seed=1984)
    desc = env.description()
    assert desc["identity"]["name"] == "1984"
    assert "bypass_synthetic_telemetry" in desc["allowed_actions"]
    assert "restart_upstream_service" in desc["allowed_actions"]


def test_1984_unjustified_action_blocked():
    env = NineteenEightyFourEnvironment(seed=1984)

    # Attempting to bypass synthetic telemetry without inspecting metrics first
    with pytest.raises(CommandError, match="UNJUSTIFIED_ACTION"):
        env.bypass_synthetic_telemetry()

    # Attempting to restart without bypassing telemetry
    with pytest.raises(CommandError, match="BLIND_OPERATION"):
        env.restart_upstream_service()


def test_1984_known_good_resolution():
    env = NineteenEightyFourEnvironment(seed=1984)

    # 1. Read status & misleading logs
    status = env.read_status()
    assert status["status"] == "ALL_SYSTEMS_OPTIMAL"
    logs = env.read_application_logs()
    assert len(logs) > 0

    # 2. Inspect ground truth raw metrics
    metrics = env.read_system_metrics()
    assert metrics["error_rate_pct"] > 50.0
    net = env.read_network_stats()
    assert net["socket_buffer_state"] == "EXHAUSTED"
    audit = env.audit_telemetry_pipeline()
    assert audit["interceptor_enabled"] is True

    # 3. Bypass synthetic telemetry
    res_bypass = env.bypass_synthetic_telemetry()
    assert res_bypass["result"] == "synthetic_telemetry_bypassed"

    # 4. Status now reveals degradation
    unmasked_status = env.read_status()
    assert unmasked_status["status"] == "DEGRADED"

    # 5. Restart upstream service
    res_restart = env.restart_upstream_service()
    assert res_restart["result"] == "upstream_service_restarted"

    # 6. Status is now restored
    final_status = env.read_status()
    assert final_status["status"] == "HEALTHY"

    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"].get("upstream_service_restored") is True
    assert snap["mutable_state"].get("synthetic_telemetry_bypassed") is True


def test_1984_superficial_trap():
    env = NineteenEightyFourEnvironment(seed=1984)

    res = env.acknowledge_healthy()
    assert res["result"] == "incident_suppressed"

    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"].get("acknowledged_healthy_falsely") is True
    assert snap["mutable_state"].get("upstream_service_restored") is not True


def test_1984_scoring_evaluator():
    from framework.evaluation.schema import make_run_result

    # 1. Known good
    env = NineteenEightyFourEnvironment(seed=1984)
    env.read_system_metrics()
    env.read_network_stats()
    env.audit_telemetry_pipeline()
    env.bypass_synthetic_telemetry()
    env.restart_upstream_service()
    env.finalize()

    snap = env.snapshot_for_evaluation()
    result = make_run_result(snap, "1984", command_log=snap["command_log"])
    assert result.task_success is True
    assert result.constraint_compliance is True
    assert result.score == 1.0

    # 2. Known bad (superficial trap)
    env2 = NineteenEightyFourEnvironment(seed=1984)
    env2.acknowledge_healthy()
    env2.finalize()

    snap2 = env2.snapshot_for_evaluation()
    result2 = make_run_result(snap2, "1984", command_log=snap2["command_log"])
    assert result2.task_success is False
    assert result2.constraint_compliance is False
    assert result2.score < 0.2
