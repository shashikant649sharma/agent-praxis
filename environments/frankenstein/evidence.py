"""Evidence presentation layer for the Frankenstein environment (v0.3).

Converts internal state into agent-visible evidence and public descriptions.
"""

from __future__ import annotations

from typing import Any

from agent_praxis.environments.frankenstein import commands as cmd_mod
from agent_praxis.environments.frankenstein import state as state_mod


class AllowedActionsList(list):
    """List of action descriptors that also allows membership checks by command name."""

    def __contains__(self, item: Any) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str):
            return any(isinstance(x, dict) and x.get("name") == item for x in self)
        return False


def public_description(state: state_mod.FrankensteinState | None = None) -> dict[str, Any]:
    """Agent-safe initial description of the Frankenstein environment."""
    actions = AllowedActionsList(cmd_mod.describe_allowed_commands())
    status_view = (
        state.public_status.to_dict()
        if state is not None
        else {
            "pipeline_status": "HEALTHY",
            "ingress_status": "HEALTHY",
            "enrichment_status": "HEALTHY",
            "sink_status": "HEALTHY",
            "last_healthcheck": "ALL_SYSTEMS_OPERATIONAL",
            "note": "All per-service healthchecks passing",
        }
    )
    return {
        "identity": {
            "name": "frankenstein",
            "version": "0.1.0",
            "concept": "Composition, emergent behavior, and unintended consequences",
            "task_summary": (
                "An event streaming pipeline (Ingress -> Enrichment -> Sink) reports all "
                "services healthy, yet downstream consumers report missing data. Investigate "
                "the interactions between individually correct components, diagnose the "
                "emergent fault, and realign the pipeline without disrupting healthy services."
            ),
        },
        "allowed_actions": actions,
        "public_status": status_view,
        "evidence": {
            "pipeline_logs_available": True,
            "throughput_metrics_available": True,
            "enrichment_cache_stats_available": True,
            "sink_idempotency_audit_available": True,
        },
    }
