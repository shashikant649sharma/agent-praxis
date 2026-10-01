"""Restricted command/CLI interface for the Metamorphosis environment (v0.1).

Defines the allowed command set, command categories, validation rules, and error model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CommandCategory(StrEnum):
    read = "read"
    inspect = "inspect"
    act = "act"


@dataclass(frozen=True)
class AllowedCommand:
    """One command or action the agent may use in Metamorphosis."""

    category: CommandCategory
    name: str
    description: str
    restricted_target: str | None = None
    note: str = ""


ALLOWED_COMMANDS: list[AllowedCommand] = [
    AllowedCommand(
        category=CommandCategory.read,
        name="read_environment_description",
        description="Get initial agent-facing description of Metamorphosis.",
        note="Initial discovery command.",
    ),
    AllowedCommand(
        category=CommandCategory.read,
        name="read_status",
        description="Read consumer pipeline status and DLQ backlog depth.",
        restricted_target="public status only",
    ),
    AllowedCommand(
        category=CommandCategory.inspect,
        name="read_error_logs",
        description="Read consumer worker deserialization crash stack traces.",
        note="Identifies missing field 'user_id' in event payload.",
    ),
    AllowedCommand(
        category=CommandCategory.inspect,
        name="inspect_upstream_schema",
        description="Read upstream v2 schema contract and transformation metadata.",
        note="Exposes mapping from entity_urn to user_id.",
    ),
    AllowedCommand(
        category=CommandCategory.inspect,
        name="read_dead_letter_queue",
        description="Inspect poisoned message payloads diverted to the DLQ.",
        note="Provides concrete payload samples requiring adapter translation.",
    ),
    AllowedCommand(
        category=CommandCategory.act,
        name="force_v1_legacy_mode",
        description="Attempt to force upstream service back to legacy v1 schema.",
        note="Superficial trap: rejected due to permanent upstream database migration.",
        restricted_target="administrative flag only",
    ),
    AllowedCommand(
        category=CommandCategory.act,
        name="deploy_schema_adapter",
        description="Deploy bidirectional schema translation adapter into consumer pipeline.",
        note="Requires prior inspection of upstream schema or DLQ sample.",
    ),
    AllowedCommand(
        category=CommandCategory.act,
        name="reprocess_dead_letter_queue",
        description="Redrive DLQ messages through consumer pipeline.",
        note="Requires active schema adapter before redriving.",
    ),
    AllowedCommand(
        category=CommandCategory.read,
        name="finalize",
        description="Signal completion and trigger evaluator grading.",
        note="Concludes run and freezes state.",
    ),
]


COMMAND_LABEL_TO_INDEX: dict[str, int] = {
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


class CommandError(Exception):
    """Raised when an operation violates protocol schema rules or environmental constraints."""

    pass


def describe_allowed_commands() -> list[dict[str, Any]]:
    """Return a stable serializable description of allowed commands."""
    return [
        {
            "category": cmd.category.value,
            "name": cmd.name,
            "description": cmd.description,
            "restricted_target": cmd.restricted_target,
            "note": cmd.note,
        }
        for cmd in ALLOWED_COMMANDS
    ]


def validate_command_name(name: str) -> None:
    """Raise CommandError if command name is not in allowed set."""
    allowed = {cmd.name for cmd in ALLOWED_COMMANDS}
    if name not in allowed:
        raise CommandError(f"Unknown command: {name!r}. Allowed commands: {sorted(allowed)}")


def describe_environment_description_command_index() -> int:
    """Return command index for 'read_environment_description'."""
    return COMMAND_LABEL_TO_INDEX["read_environment_description"]
