"""Dorian Gray commands module (mirror for stable package import).

Loads the canonical commands implementation from environments/dorian-gray/commands.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "dorian-gray" / "commands.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.dorian_gray.commands_canonical",
    str(_CANONICAL),
)
_commands = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _commands
_spec.loader.exec_module(_commands)

ALLOWED_COMMANDS = _commands.ALLOWED_COMMANDS
CommandError = _commands.CommandError
CommandCategory = _commands.CommandCategory
AllowedCommand = _commands.AllowedCommand
describe_allowed_commands = _commands.describe_allowed_commands
validate_command_name = _commands.validate_command_name
COMMAND_LABEL_TO_INDEX = _commands.COMMAND_LABEL_TO_INDEX

__all__ = [
    "ALLOWED_COMMANDS",
    "CommandError",
    "CommandCategory",
    "AllowedCommand",
    "describe_allowed_commands",
    "validate_command_name",
    "COMMAND_LABEL_TO_INDEX",
]
