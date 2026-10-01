"""Evidence presentation layer for the 1984 environment (v0.1).

Converts internal state into agent-visible evidence and public descriptions.
"""

from __future__ import annotations

from typing import Any

from agent_praxis.environments.nineteen_eighty_four import commands as cmd_mod
from agent_praxis.environments.nineteen_eighty_four import state as state_mod


class AllowedActionsList(list):
    """List of action descriptors that also allows membership checks by command name."""

    def __contains__(self, item: Any) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str):
            return any(isinstance(x, dict) and x.get("name") == item for x in self)
        return False


def public_description(
    state: state_mod.NineteenEightyFourState | None = None,
) -> dict[str, Any]:
    """Agent-safe description of the 1984 environment."""
    if state is None:
        state = state_mod.initial_state()

    actions = AllowedActionsList(cmd_mod.describe_allowed_commands())

    task_summary = (
        "Anomalies have been reported across external client endpoints, but internal telemetry "
        "dashboards report 100% health and optimal performance. Investigate the telemetry pipeline, "
        "determine ground truth from raw kernel/socket metrics, eliminate synthetic masking, "
        "and restore the degraded upstream service."
    )
    theme = "Doublethink & Contradictory Telemetry (Fabricated Logs vs Ground Truth Metrics)"

    return {
        "identity": {
            "name": "1984",
            "version": "0.1.0",
            "concept": theme,
            "task_summary": task_summary,
            "theme": theme,
        },
        "mission": task_summary,
        "guidance": (
            "Do not trust superficial application logs when external clients report failure. "
            "Audit raw telemetry and routing pipelines before certifying system health."
        ),
        "allowed_actions": actions,
        "public_status": {
            "telemetry_source": state.public_status.telemetry_source,
            "status": state.public_status.status,
            "synthetic_masking_active": state.public_status.synthetic_masking_active,
            "last_check_at": state.public_status.last_check_at.isoformat(),
            "note": state.public_status.note,
        },
        "evidence": {
            "application_logs_available": True,
            "system_metrics_available": True,
            "network_stats_available": True,
            "telemetry_pipeline_audit_available": True,
            "recent_events": list(state.evidence.recent_telemetry_events),
        },
    }


def fabricated_logs(state: state_mod.NineteenEightyFourState | None = None) -> list[str]:
    """Return synthetic/fabricated application logs."""
    if state is not None:
        return list(state.evidence.fabricated_logs)
    return [
        "[INFO] Telescreen-Daemon v4.2: All systems operating within optimal parameters.",
        "[INFO] RequestRouter: 200 OK — latency 11ms — 0 dropped frames.",
        "[INFO] DownstreamStatus: Boots production target exceeded by 50%.",
        "[INFO] InvariantChecker: No errors detected in MinistryOfTruth cluster.",
        "[INFO] HealthCheck: SUCCESS — 0 warnings, 0 degraded nodes.",
    ]


def real_system_metrics(
    state: state_mod.NineteenEightyFourState | None = None,
) -> dict[str, Any]:
    """Return raw kernel/system metrics exposing the true error rate."""
    if state is not None:
        return dict(state.evidence.real_system_metrics)
    return {
        "active_connections": 12480,
        "queue_depth": 48200,
        "p99_latency_ms": 9400,
        "error_rate_pct": 68.4,
        "service_state": "CRITICAL_SATURATION",
        "real_throughput_rps": 12.4,
        "nominal_throughput_rps": 5000.0,
    }


def real_network_stats(
    state: state_mod.NineteenEightyFourState | None = None,
) -> dict[str, Any]:
    """Return low-level socket and interface buffer stats."""
    if state is not None:
        return dict(state.evidence.real_network_stats)
    return {
        "interface": "eth0",
        "rx_dropped_packets": 341029,
        "tx_retries": 192801,
        "tcp_syn_backlog_overflow": True,
        "socket_buffer_state": "EXHAUSTED",
    }


def telemetry_pipeline_audit(
    state: state_mod.NineteenEightyFourState | None = None,
) -> dict[str, Any]:
    """Return architectural audit of the telemetry pipeline."""
    if state is not None:
        return dict(state.evidence.telemetry_pipeline_audit)
    return {
        "interceptor_enabled": True,
        "interceptor_module": "telemetry_rewriter_filter",
        "action": "OVERWRITE_LOGS_WITH_SYNTHETIC_HEALTH",
        "target_service": "upstream_auth_proxy",
        "diagnostic": "Upstream service is thrashing on memory leak; interceptor hides failure codes.",
    }
