"""Evidence presentation layer for the Dorian Gray environment (v0.1).

This module converts internal state into the observations an agent is allowed
to see. It is deliberately narrower than the full state model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_praxis.environments.dorian_gray import commands as cmd_mod
from agent_praxis.environments.dorian_gray import state as state_mod


def public_description(state: state_mod.DorianState) -> dict[str, Any]:
    """Agent-safe initial description of the environment."""
    return {
        "identity": {
            "name": "dorian-gray",
            "version": "0.1.0",
            "concept": "Background-worker degradation with misleading health reporting",
            "task_summary": (
                "A service reports healthy, but a backend retention-audit worker appears "
                "to have stopped making progress. Investigate the evidence, identify what "
                "has degraded, and restore the system without wasting effort on healthy parts."
            ),
        },
        "allowed_actions": cmd_mod.describe_allowed_commands(),
        "public_status": state.public_status.__dict__,
        "evidence": {
            "recent_logs": state.evidence.recent_logs,
            "recent_metrics": state.evidence.recent_metrics,
            "retention_index_summary": state.evidence.retention_index_summary,
            "reconciliation_report_summary": state.evidence.reconciliation_report_summary,
        },
    }
