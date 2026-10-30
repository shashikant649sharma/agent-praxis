"""Unified Observation Interface Schema v1.0 for Agent Praxis.

Provides a shared outer schema envelope across all 10 environments while preserving
environment-specific observational payloads.
The observation envelope and action menus are generated dynamically from the single source of truth
(canonical action registry), strictly isolating hidden evaluator state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from agent_praxis.actions import CANONICAL_ACTION_ORDER


@dataclass(frozen=True)
class UnifiedObservation:
    """Standardized schema v1.0 observation envelope."""

    schema_version: str = "1.0"
    environment_id: str = ""
    episode_id: str = ""
    identity: dict[str, Any] = field(default_factory=dict)
    public_status: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=list)
    environment_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the observation envelope to a serializable dictionary."""
        return asdict(self)


def get_available_actions_for_environment(environment_id: str) -> list[str]:
    """Retrieve dynamically allowable actions directly from canonical registry."""
    norm_id = environment_id.lower().replace("_", "-")
    return list(CANONICAL_ACTION_ORDER.get(norm_id, ()))


def build_unified_observation(
    environment_id: str,
    env_instance: Any,
    episode_id: str = "ep-default",
    step_count: int = 0,
    current_action_result: Any | None = None,
) -> UnifiedObservation:
    """Build a compliant UnifiedObservation envelope for any Agent Praxis environment."""
    norm_id = environment_id.lower().replace("_", "-")
    available_actions = get_available_actions_for_environment(norm_id)

    state = getattr(env_instance, "_state", None)

    # 1. Identity
    identity: dict[str, Any] = {}
    if hasattr(env_instance, "identity"):
        id_val = env_instance.identity
        if hasattr(id_val, "__dict__"):
            identity = {k: v for k, v in id_val.__dict__.items() if not k.startswith("_")}
        elif isinstance(id_val, dict):
            identity = dict(id_val)

    # 2. Public Status
    public_status: dict[str, Any] = {}
    if state is not None and hasattr(state, "public_status"):
        ps = state.public_status
        if hasattr(ps, "__dict__"):
            public_status = {k: v for k, v in ps.__dict__.items() if not k.startswith("_")}
        elif isinstance(ps, dict):
            public_status = dict(ps)

    # 3. Evidence
    evidence_list: list[dict[str, Any]] = []
    if state is not None and hasattr(state, "evidence"):
        ev = state.evidence
        if isinstance(ev, list):
            for item in ev:
                if hasattr(item, "__dict__"):
                    evidence_list.append(
                        {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
                    )
                elif isinstance(item, dict):
                    evidence_list.append(dict(item))

    # 4. Environment State (Sanitized agent-facing view, excluding private/evaluator fields)
    env_state: dict[str, Any] = {}
    if current_action_result is not None:
        if isinstance(current_action_result, dict):
            env_state = {k: v for k, v in current_action_result.items() if not k.startswith("_")}
        else:
            env_state = {"result": str(current_action_result)}
    elif hasattr(env_instance, "read_status"):
        try:
            status_res = env_instance.read_status()
            if isinstance(status_res, dict):
                env_state = {k: v for k, v in status_res.items() if not k.startswith("_")}
        except Exception:
            pass

    # 5. Metadata
    metadata = {
        "step_count": step_count,
        "variant": getattr(env_instance, "variant", getattr(env_instance, "_variant", "standard")),
        "seed": getattr(env_instance, "seed", getattr(env_instance, "_seed", 0)),
    }

    return UnifiedObservation(
        schema_version="1.0",
        environment_id=norm_id,
        episode_id=episode_id,
        identity=identity,
        public_status=public_status,
        evidence=evidence_list,
        available_actions=available_actions,
        environment_state=env_state,
        metadata=metadata,
    )
