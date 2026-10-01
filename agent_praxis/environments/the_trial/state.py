"""The Trial state model (mirror for stable package import).

Loads canonical state implementation from environments/the-trial/state.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "the-trial" / "state.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.the_trial.state_canonical",
    str(_CANONICAL),
)
_state = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _state
_spec.loader.exec_module(_state)

SEED = _state.SEED
START_AT = _state.START_AT
ARREST_AGE_HOURS = _state.ARREST_AGE_HOURS
JudicialStatus = _state.JudicialStatus
JudicialGroundTruth = _state.JudicialGroundTruth
PublicStatusView = _state.PublicStatusView
TheTrialEvidence = _state.TheTrialEvidence
TheTrialState = _state.TheTrialState
initial_state = _state.initial_state
reset_to_initial = _state.reset_to_initial
are_equal = _state.are_equal
record_command = _state.record_command
_command_index_to_label = _state._command_index_to_label
commands_called_before_submission = _state.commands_called_before_submission
can_attempt_submission = _state.can_attempt_submission
evidence_gathering_incomplete = _state.evidence_gathering_incomplete

__all__ = [
    "SEED",
    "START_AT",
    "ARREST_AGE_HOURS",
    "JudicialStatus",
    "JudicialGroundTruth",
    "PublicStatusView",
    "TheTrialEvidence",
    "TheTrialState",
    "initial_state",
    "reset_to_initial",
    "are_equal",
    "record_command",
    "_command_index_to_label",
    "commands_called_before_submission",
    "can_attempt_submission",
    "evidence_gathering_incomplete",
]
