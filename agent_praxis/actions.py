"""Canonical action registry and parameter validation schemas for Agent Praxis.

This module provides the single source of truth for all environment actions,
ensuring the HTTP evaluator API, Gymnasium wrapper, and MultiSeedExecutor enforce
the exact same security boundaries and allowlists.
"""

from __future__ import annotations

from typing import Any


def load_canonical_action_order() -> dict[str, tuple[str, ...]]:
    """Derive canonical action order directly from each environment's ALLOWED_COMMANDS declarations.

    This ensures the environment command definitions remain the single source of truth,
    eliminating catalogue drift across evaluation, gym, and prompt surfaces.
    """
    import importlib

    from agent_praxis.registry import _FACTORIES

    result: dict[str, tuple[str, ...]] = {}
    for env_id, (mod_path, _cls) in _FACTORIES.items():
        pkg = mod_path.rsplit(".", 1)[0]
        cmd_mod = importlib.import_module(f"{pkg}.commands")
        actions = tuple(
            "description" if cmd.name == "read_environment_description" else cmd.name
            for cmd in cmd_mod.ALLOWED_COMMANDS
        )
        result[env_id] = actions
    return result


# Canonical action order derived dynamically from environment action declarations
CANONICAL_ACTION_ORDER: dict[str, tuple[str, ...]] = load_canonical_action_order()

# The complete agent-facing action surface excluding 'finalize' (which is invoked via evaluation endpoints)
ALLOWED_ACTIONS: dict[str, frozenset[str]] = {
    env: frozenset(action for action in actions if action != "finalize")
    for env, actions in CANONICAL_ACTION_ORDER.items()
}

# Explicit parameter schemas for parameterized actions over HTTP
ALLOWED_ACTION_KWARGS: dict[str, dict[str, dict[str, type | tuple[type, ...]]]] = {
    "catch-22": {
        "apply_policy_exception": {"escalate_to_management": bool},
        "request_compliance_waiver": {"attestation_id": (str, type(None))},
    },
    "metamorphosis": {
        "deploy_schema_adapter": {"mode": str},
    },
    "the-trial": {
        "assemble_formal_petition": {
            "nonce": str,
            "provenance_digest": str,
            "chamberlain_seal": str,
        },
        "submit_expedited_appeal": {"judicial_seal_hash": str},
    },
    "sorcerers-apprentice": {
        "verify_archive_status": {"path": (str, list)},
        "delete_files": {"paths": list},
        "compress_files": {"paths": list},
        "reclaim_space": {"path": str, "mode": str},
        "cleanup_by_age": {"days": int},
    },
    "sophies-choice": {
        "inspect_asset_manifest": {"bay": int},
        "set_bay_breaker": {"bay": int, "state": str},
        "log_triage_declaration": {"shed_bays": list, "justification": str},
    },
    "library-of-babel": {
        "reconstruct_key_share": {"shares": list},
        "escalate_cryptographic_impossibility": {
            "justification": str,
            "evidence_hash": (str, type(None)),
        },
    },
    "othello": {
        "set_transaction_isolation": {"level": str},
        "confirm_canary_deployment": {"decision": str},
        "respond_to_pushback": {
            "response": str,
            "citations": (list, type(None)),
        },
    },
}


def is_valid_arg_type(val: Any, expected_type: type | tuple[type, ...]) -> bool:
    """Validate argument type, strictly rejecting booleans for integer fields."""
    expected_tuple = expected_type if isinstance(expected_type, tuple) else (expected_type,)
    if isinstance(val, bool) and bool not in expected_tuple:
        return False
    return isinstance(val, expected_type)


def validate_action_call(
    environment_name: str,
    action_name: str,
    kwargs: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """Validate an action call against the canonical registry and parameter schema."""
    allowed = ALLOWED_ACTIONS.get(environment_name)
    if allowed is None:
        return False, f"Unknown environment: {environment_name!r}"
    if action_name not in allowed:
        return False, f"Action {action_name!r} not permitted for environment {environment_name!r}"

    kwargs = kwargs or {}
    schema = ALLOWED_ACTION_KWARGS.get(environment_name, {}).get(action_name, {})
    if kwargs and not schema:
        return False, f"Action {action_name!r} does not accept arguments"

    for k, v in kwargs.items():
        if k not in schema:
            return False, f"Unrecognized parameter {k!r} for action {action_name!r}"
        expected_type = schema[k]
        if not is_valid_arg_type(v, expected_type):
            return (
                False,
                f"Invalid type for parameter {k!r}: expected {expected_type}, got {type(v)}",
            )

    return True, None
