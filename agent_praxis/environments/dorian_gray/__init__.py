"""Agent Praxis environments package.

Note: the canonical environment source tree lives under environments/ (kebab-case
directories). This package re-exposes the current environment surface so
repository commands and tests can import from a stable package path without
renaming directories mid-v0.1.

For v0.1, we mirror the Dorian Gray state/evidence/commands/environment modules
into this package so the import graph `agent_praxis.environments.dorian_gray`
is stable during development. The environments/dorian-gray/ directory remains the
specification and implementation source of truth.
"""

from agent_praxis.environments.dorian_gray import commands as _commands
from agent_praxis.environments.dorian_gray import evidence as _evidence
from agent_praxis.environments.dorian_gray import state as _state
from agent_praxis.environments.dorian_gray import environment as _environment

# Expose a stable public surface from the canonical modules.
commands = _commands
evidence = _evidence
state = _state
environment = _environment

__all__ = ["commands", "evidence", "state", "environment"]
