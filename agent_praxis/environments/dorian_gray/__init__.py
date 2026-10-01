"""Dorian Gray environment package (mirror for stable package import).

The mirror imports the canonical implementation from environments/dorian-gray/
via the individual mirror modules (state, commands, evidence, environment),
which each load their canonical source via importlib.
"""

from agent_praxis.environments.dorian_gray import commands, environment, evidence, state

__all__ = ["commands", "environment", "evidence", "state"]
