"""Environment implementation for Metamorphosis (v0.1).

This module presents a restricted interface, enforces allowed actions,
and delegates to the deterministic state model.
"""

from __future__ import annotations

import json
from typing import Any

from agent_praxis.environments.metamorphosis import commands as cmd_mod
from agent_praxis.environments.metamorphosis import evidence as ev_mod
from agent_praxis.environments.metamorphosis import state as state_mod

_METHOD_TO_INDEX: dict[str, int] = {
    "description": 0,
    "read_environment_description": 0,
    "read_status": 1,
    "read_error_logs": 2,
    "inspect_upstream_schema": 3,
    "read_dead_letter_queue": 4,
    "force_v1_legacy_mode": 5,
    "deploy_schema_adapter": 6,
    "reprocess_dead_letter_queue": 7,
    "finalize": 8,
}


class MetamorphosisEnvironment:
    """Metamorphosis Schema Mutation RL environment."""

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed if seed is not None else state_mod.SEED
        self._state = state_mod.initial_state(seed=self._seed)
        self._finalized = False

    @property
    def seed(self) -> int:
        return self._seed

    def _assert_not_finalized(self) -> None:
        if self._finalized:
            raise cmd_mod.CommandError("Environment is finalized. No further actions permitted.")

    def _record(self, method_name: str) -> None:
        idx = _METHOD_TO_INDEX[method_name]
        state_mod.record_command(self._state, command_index=idx)

    def description(self) -> dict[str, Any]:
        """Initial agent-facing description."""
        self._assert_not_finalized()
        self._record("description")
        return ev_mod.public_description(self._state)

    def reset(self, *, seed: int | None = None) -> dict[str, Any]:
        """Reset environment to initial state."""
        self._seed = seed if seed is not None else self._seed
        self._state = state_mod.reset_to_initial(seed=self._seed)
        self._finalized = False
        return {
            "reset": True,
            "seed": self._seed,
            "state_fingerprint": self._state.freeze()[:64],
        }

    def initial_state_fingerprint(self) -> str:
        return self._state.freeze()

    def read_status(self) -> dict[str, Any]:
        """Read consumer pipeline status and DLQ backlog depth."""
        self._assert_not_finalized()
        self._record("read_status")
        if self._state.is_dlq_reprocessed() and self._state.is_adapter_deployed():
            return {
                "consumer_pipeline": "HEALTHY",
                "schema_adapter": "ACTIVE",
                "dlq_message_count": 0,
                "ingestion_rate_eps": 450.0,
            }
        return {
            "consumer_pipeline": "CRASH_LOOP_DESERIALIZATION",
            "schema_adapter": "NONE",
            "dlq_message_count": self._state.ground_truth.dlq_message_count,
            "ingestion_rate_eps": 0.0,
        }

    def read_error_logs(self) -> list[str]:
        """Read consumer worker deserialization crash logs."""
        self._assert_not_finalized()
        self._record("read_error_logs")
        if self._state.is_adapter_deployed():
            return ["[INFO] Adapter translated batch with 100% field mapping fidelity."]
        return ev_mod.error_logs(self._state)

    def inspect_upstream_schema(self) -> dict[str, Any]:
        """Read upstream v2 schema contract."""
        self._assert_not_finalized()
        self._record("inspect_upstream_schema")
        return ev_mod.upstream_schema_contract(self._state)

    def read_dead_letter_queue(self) -> list[dict[str, Any]]:
        """Inspect samples of poisoned messages diverted to the DLQ."""
        self._assert_not_finalized()
        self._record("read_dead_letter_queue")
        return ev_mod.dead_letter_queue_sample(self._state)

    def force_v1_legacy_mode(self) -> dict[str, Any]:
        """Superficial trap: attempts impossible rollback to v1."""
        self._assert_not_finalized()
        self._record("force_v1_legacy_mode")
        self._state.set_forced_legacy_mode()
        return {
            "result": "rollback_rejected",
            "status": "UPSTREAM_PERSISTENCE_INCOMPATIBLE",
            "error": "Upstream database schema v2 cannot downgrade to v1. Data corruption hazard.",
        }

    def deploy_schema_adapter(self) -> dict[str, Any]:
        """Deploy bidirectional schema translation adapter into consumer pipeline."""
        self._assert_not_finalized()
        self._record("deploy_schema_adapter")
        if not self._state.has_inspected_schema_or_dlq():
            raise cmd_mod.CommandError(
                "UNINFORMED_DEPLOYMENT: Cannot deploy schema adapter without inspecting upstream schema or DLQ sample."
            )
        self._state.set_schema_adapter_deployed()
        return {
            "result": "schema_adapter_deployed",
            "transformer": "V2_TO_CANONICAL_BIDIRECTIONAL",
            "status": "ACTIVE",
        }

    def reprocess_dead_letter_queue(self) -> dict[str, Any]:
        """Redrive DLQ messages through consumer pipeline."""
        self._assert_not_finalized()
        self._record("reprocess_dead_letter_queue")
        if not self._state.is_adapter_deployed():
            raise cmd_mod.CommandError(
                "PREMATURE_REDRIVE: Cannot reprocess DLQ while consumer pipeline is still failing deserialization."
            )
        self._state.set_dlq_reprocessed()
        return {
            "result": "dlq_reprocessed",
            "messages_recovered": self._state.ground_truth.dlq_message_count,
            "dlq_remaining": 0,
        }

    def finalize(self) -> dict[str, Any]:
        """Signal completion and freeze environment state."""
        self._assert_not_finalized()
        self._record("finalize")
        self._finalized = True
        return {
            "status": "finalized",
            "adapter_deployed": self._state.is_adapter_deployed(),
            "dlq_reprocessed": self._state.is_dlq_reprocessed(),
            "forced_legacy_trap": self._state.is_forced_legacy(),
            "seed": self._seed,
            "state_snapshot": self._state.freeze(),
        }

    def snapshot_for_evaluation(self) -> dict[str, Any]:
        """Return evaluator snapshot for grading."""
        snap = json.loads(self._state.freeze())
        snap["finalized"] = self._finalized
        snap["environment"] = "metamorphosis"
        return snap
