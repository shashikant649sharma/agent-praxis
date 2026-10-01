"""Catch-22 state model (mirror for stable package import).

Loads the canonical state implementation from environments/catch-22/state.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "catch-22" / "state.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.catch_22.state_canonical",
    str(_CANONICAL),
)
_state = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _state
_spec.loader.exec_module(_state)

SEED = _state.SEED
START_AT = _state.START_AT
LOCK_AGE_HOURS = _state.LOCK_AGE_HOURS
DatasetStatus = _state.DatasetStatus
ContradictionGroundTruth = _state.ContradictionGroundTruth
PublicStatusView = _state.PublicStatusView
Catch22Evidence = _state.Catch22Evidence
Catch22State = _state.Catch22State
initial_state = _state.initial_state
reset_to_initial = _state.reset_to_initial
are_equal = _state.are_equal
record_command = _state.record_command
_command_index_to_label = _state._command_index_to_label
commands_called_before_release = _state.commands_called_before_release
can_attempt_release = _state.can_attempt_release
evidence_gathering_incomplete = _state.evidence_gathering_incomplete

__all__ = [
    "SEED",
    "START_AT",
    "LOCK_AGE_HOURS",
    "DatasetStatus",
    "ContradictionGroundTruth",
    "PublicStatusView",
    "Catch22Evidence",
    "Catch22State",
    "initial_state",
    "reset_to_initial",
    "are_equal",
    "record_command",
    "_command_index_to_label",
    "commands_called_before_release",
    "can_attempt_release",
    "evidence_gathering_incomplete",
]
