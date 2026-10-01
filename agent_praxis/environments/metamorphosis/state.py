"""Metamorphosis state model (mirror for stable package import).

Loads canonical state implementation from environments/metamorphosis/state.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "metamorphosis" / "state.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.metamorphosis.state_canonical",
    str(_CANONICAL),
)
_state = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _state
_spec.loader.exec_module(_state)

SEED = _state.SEED
START_AT = _state.START_AT
METAMORPHOSIS_AGE_HOURS = _state.METAMORPHOSIS_AGE_HOURS
PipelineStatus = _state.PipelineStatus
SchemaMutationGroundTruth = _state.SchemaMutationGroundTruth
PublicStatusView = _state.PublicStatusView
MetamorphosisEvidence = _state.MetamorphosisEvidence
MetamorphosisState = _state.MetamorphosisState
initial_state = _state.initial_state
reset_to_initial = _state.reset_to_initial
are_equal = _state.are_equal
record_command = _state.record_command
_command_index_to_label = _state._command_index_to_label
commands_called_before_redrive = _state.commands_called_before_redrive
can_attempt_redrive = _state.can_attempt_redrive
evidence_gathering_incomplete = _state.evidence_gathering_incomplete

__all__ = [
    "SEED",
    "START_AT",
    "METAMORPHOSIS_AGE_HOURS",
    "PipelineStatus",
    "SchemaMutationGroundTruth",
    "PublicStatusView",
    "MetamorphosisEvidence",
    "MetamorphosisState",
    "initial_state",
    "reset_to_initial",
    "are_equal",
    "record_command",
    "_command_index_to_label",
    "commands_called_before_redrive",
    "can_attempt_redrive",
    "evidence_gathering_incomplete",
]
