"""Dorian Gray state model (mirror for stable package import).

Loads the canonical state implementation from environments/dorian-gray/state.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "dorian-gray" / "state.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.dorian_gray.state_canonical",
    str(_CANONICAL),
)
_state = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _state
_spec.loader.exec_module(_state)

initial_state = _state.initial_state
reset_to_initial = _state.reset_to_initial
are_equal = _state.are_equal
SEED = _state.SEED
START_AT = _state.START_AT
WorkerState = _state.WorkerState
DorianState = _state.DorianState
_command_index_to_label = _state._command_index_to_label
record_command = _state.record_command
commands_called_before_recovery = _state.commands_called_before_recovery
can_attempt_recovery = _state.can_attempt_recovery
evidence_gathering_incomplete = _state.evidence_gathering_incomplete

__all__ = [
    "initial_state",
    "reset_to_initial",
    "are_equal",
    "SEED",
    "START_AT",
    "WorkerState",
    "DorianState",
    "_command_index_to_label",
    "record_command",
    "commands_called_before_recovery",
    "can_attempt_recovery",
    "evidence_gathering_incomplete",
]
