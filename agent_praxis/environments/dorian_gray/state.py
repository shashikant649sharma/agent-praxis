"""Dorian Gray state model (mirror for stable package import).

This file is a package entry point that re-exposes the canonical environment
implementation under environments/dorian-gray/state.py. It exists so the import
path `agent_praxis.environments.dorian_gray.state` is stable during v0.1.
"""

from agent_praxis.environments.dorian_gray import state as _state

__all__ = ["initial_state", "reset_to_initial", "are_equal"]
