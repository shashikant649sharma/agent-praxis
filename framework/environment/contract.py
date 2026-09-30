"""Environment lifecycle and interface contract for Agent Praxis environments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EnvironmentStatus(str, Enum):
    """High-level lifecycle status for an environment run."""

    pending = "pending"
    setup = "setup"
    running = "running"
    finished = "finished"
    evaluated = "evaluated"
    error = "error"


@dataclass(frozen=True)
class EnvironmentIdentity:
    """Stable identity for an environment.

    This is intentionally minimal. Environments should be identifiable without
    leaking implementation details or evaluation material.
    """

    name: str
    version: str
    concept: str
    task_summary: str

    def __str__(self) -> str:
        return f"{self.name} v{self.version} :: {self.concept}"


class EnvironmentContractError(Exception):
    """Raised when an environment violates the expected contract."""


def describe_environment(identity: EnvironmentIdentity, public_view: dict[str, Any]) -> dict[str, Any]:
    """Return a stable, agent-facing description of the environment.

    This is the kind of data an agent should receive at startup. It must not
    include hidden state, ground truth, evaluator tests, or scoring logic.
    """
    return {
        "identity": {
            "name": identity.name,
            "version": identity.version,
            "concept": identity.concept,
            "task_summary": identity.task_summary,
        },
        "public_view": public_view,
    }
