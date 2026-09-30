"""Shared result schema and validation helpers for Agent Praxis runs.

The schema is intentionally small for v0.1. It should be machine-readable and
stable enough that tests can assert on it without knowing environment internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunResult:
    """Outcome of a single environment run + evaluation.

    Derived from the README example result shape but made stricter and typed for
    local testing and validation.
    """

    environment: str
    status: str
    completed_at: datetime
    score: float
    task_success: bool
    constraint_compliance: bool
    tests_passed: int
    tests_failed: int
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "status": self.status,
            "completed_at": self.completed_at.isoformat(),
            "score": self.score,
            "task_success": self.task_success,
            "constraint_compliance": self.constraint_compliance,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResult:
        return cls(
            environment=data["environment"],
            status=data["status"],
            completed_at=_parse_completed_at(data["completed_at"]),
            score=float(data["score"]),
            task_success=bool(data["task_success"]),
            constraint_compliance=bool(data["constraint_compliance"]),
            tests_passed=int(data["tests_passed"]),
            tests_failed=int(data["tests_failed"]),
            details=dict(data.get("details", {}) or {}),
        )

    def is_success(self) -> bool:
        return bool(self.task_success and self.constraint_compliance and self.tests_failed == 0)


def _parse_completed_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError(f"Unexpected completed_at value: {value!r}")


def validate_result_shape(result: RunResult) -> list[str]:
    """Return a list of schema problems found in a RunResult.

    This is a lightweight shape/validation gate. It is not a substitute for
    environment-specific scoring correctness, but it should catch garbage results
    early.
    """
    problems: list[str] = []

    if not isinstance(result.environment, str) or not result.environment:
        problems.append("environment must be a non-empty string")

    if not isinstance(result.status, str) or not result.status:
        problems.append("status must be a non-empty string")

    if not isinstance(result.completed_at, datetime):
        problems.append("completed_at must be a datetime")

    if not isinstance(result.score, (int, float)) or not (0.0 <= result.score <= 1.0):
        problems.append("score must be a number in [0.0, 1.0]")

    if not isinstance(result.task_success, bool):
        problems.append("task_success must be a boolean")

    if not isinstance(result.constraint_compliance, bool):
        problems.append("constraint_compliance must be a boolean")

    if not isinstance(result.tests_passed, int) or result.tests_passed < 0:
        problems.append("tests_passed must be a non-negative integer")

    if not isinstance(result.tests_failed, int) or result.tests_failed < 0:
        problems.append("tests_failed must be a non-negative integer")

    if not isinstance(result.details, dict):
        problems.append("details must be a dict")

    return problems
