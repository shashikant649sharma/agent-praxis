"""Shared exception types for the Agent Praxis client SDK.

Kept dependency-free on purpose: the agent-side HTTP client must be installable
into a minimal container without the environment implementations, the scoring
logic, or any hidden ground-truth state.  The environment packages re-export
``CommandError`` from here so that agent code and evaluator code refer to a
single exception type.
"""

from __future__ import annotations


class CommandError(Exception):
    """Raised when an agent attempts a disallowed, malformed, or invalid action."""


__all__ = ["CommandError"]
