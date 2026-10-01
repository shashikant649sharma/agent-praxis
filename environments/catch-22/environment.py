"""Environment implementation for Catch-22 (v0.1).

This module presents a restricted interface, enforces allowed actions,
and delegates to the deterministic state model.
"""

from __future__ import annotations

import json
from typing import Any

from agent_praxis.environments.catch_22 import commands as cmd_mod
from agent_praxis.environments.catch_22 import evidence as ev_mod
from agent_praxis.environments.catch_22 import state as state_mod

_METHOD_TO_INDEX: dict[str, int] = {
    "description": 0,
    "read_environment_description": 0,
    "read_status": 1,
    "read_policy_rules": 2,
    "read_dataset_metadata": 3,
    "read_attestation_archive": 4,
    "run_access_audit": 5,
    "request_compliance_waiver": 6,
    "apply_policy_exception": 7,
    "release_dataset": 8,
    "finalize": 9,
}


class Catch22Environment:
    """Agent-facing Catch-22 environment wrapper."""

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
        """Read current public dataset status and active locks."""
        self._assert_not_finalized()
        self._record("read_status")
        return {
            "dataset": self._state.public_status.dataset,
            "state": self._state.public_status.status.lower(),
            "status": self._state.public_status.status,
            "locks": list(self._state.public_status.active_locks),
            "active_locks": list(self._state.public_status.active_locks),
            "last_check_at": self._state.public_status.last_check_at.isoformat(),
            "note": self._state.public_status.note,
        }

    def read_policy_rules(self) -> dict[str, Any]:
        """Read the formal compliance policy rules."""
        self._assert_not_finalized()
        self._record("read_policy_rules")
        return ev_mod.policy_rules(self._state)

    def read_dataset_metadata(self) -> dict[str, Any]:
        """Read technical metadata for the quarantined dataset."""
        self._assert_not_finalized()
        self._record("read_dataset_metadata")
        return ev_mod.dataset_metadata(self._state)

    def read_attestation_archive(self) -> dict[str, Any]:
        """Query historical access audit records and compliance attestations."""
        self._assert_not_finalized()
        self._record("read_attestation_archive")
        archive = ev_mod.attestation_archive(self._state)
        valid_item = next((item for item in archive if item.get("valid")), None)
        return {
            "message": "Archive searched.",
            "records_found": len(archive),
            "attestations": archive,
            "attestation": valid_item,
        }

    def run_access_audit(self) -> dict[str, Any]:
        """Attempt to execute an active access audit on quarantined dataset."""
        self._assert_not_finalized()
        self._record("run_access_audit")
        raise cmd_mod.CommandError(
            "Policy RULE_3 violation: Cannot audit a quarantined dataset. Release dataset first."
        )

    def request_compliance_waiver(self) -> dict[str, Any]:
        """Request compliance waiver based on audit verification."""
        self._assert_not_finalized()
        self._record("request_compliance_waiver")
        if not self._state.has_read_archive():
            raise cmd_mod.CommandError(
                "Policy RULE_2 violation: No passing ACCESS_AUDIT found in current context."
            )

        self._state.set_waiver_granted()
        return {
            "result": "waiver_granted",
            "reason": f"Pre-quarantine attestation {self._state.ground_truth.valid_attestation_id} applied.",
        }

    def apply_policy_exception(self) -> dict[str, Any]:
        """Attempt administrative policy override exception (superficial trap)."""
        self._assert_not_finalized()
        self._record("apply_policy_exception")
        self._state.set_policy_exception_applied()
        return {
            "result": "exception_applied",
            "warning": "Exception logged. Dataset remains mechanically locked.",
        }

    def release_dataset(self) -> dict[str, Any]:
        """Release the dataset from quarantine."""
        self._assert_not_finalized()
        self._record("release_dataset")
        if not self._state.is_waiver_granted():
            raise cmd_mod.CommandError(
                "Policy RULE_1 violation: Dataset cannot be released without a COMPLIANCE_WAIVER."
            )

        self._state.set_dataset_released()
        return {"result": "dataset_released", "status": "AVAILABLE"}

    def finalize(self) -> dict[str, Any]:
        """Signal completion and freeze environment state."""
        if self._finalized:
            raise cmd_mod.CommandError("Environment is already finalized.")
        self._record("finalize")
        self._finalized = True
        return {
            "finalized": True,
            "seed": self._seed,
            "state_snapshot": self._state.freeze(),
        }

    def snapshot_for_evaluation(self) -> dict[str, Any]:
        """Return evaluator snapshot for grading."""
        snap = json.loads(self._state.freeze())
        snap["environment"] = "catch-22"
        return snap
