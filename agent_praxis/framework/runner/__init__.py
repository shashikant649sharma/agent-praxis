"""Agent Praxis framework runner sub-package — loads canonical helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "framework" / "runner" / "helpers.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.runner.helpers_canonical",
    str(_CANONICAL),
)
_helpers = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _helpers
_spec.loader.exec_module(_helpers)

helpers = _helpers

__all__ = ["helpers"]
