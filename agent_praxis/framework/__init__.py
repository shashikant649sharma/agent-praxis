"""Agent Praxis framework package — shim that loads canonical source trees.

The canonical framework source lives under framework/ at the repo root.
This package makes it importable as agent_praxis.framework.*.
"""

from agent_praxis.framework.environment import contract  # noqa: F401
from agent_praxis.framework.evaluation import schema, validation  # noqa: F401
from agent_praxis.framework.runner import helpers  # noqa: F401

__all__ = ["contract", "schema", "validation", "helpers"]
