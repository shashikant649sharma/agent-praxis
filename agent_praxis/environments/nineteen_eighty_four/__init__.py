"""1984 environment package (mirror for stable package import).

The mirror imports the canonical implementation from environments/1984/
via the individual mirror modules (state, commands, evidence, environment),
which each load their canonical source via importlib.
"""

from agent_praxis.environments.nineteen_eighty_four import (
    commands,
    environment,
    evidence,
    state,
)

__all__ = ["commands", "environment", "evidence", "state"]
