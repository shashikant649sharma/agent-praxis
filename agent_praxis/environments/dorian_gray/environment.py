"""Dorian Gray environment wrapper (mirror for stable package import).

Loads the canonical environment implementation from environments/dorian-gray/environment.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "dorian-gray" / "environment.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.dorian_gray.environment_canonical",
    str(_CANONICAL),
)
_env = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _env
_spec.loader.exec_module(_env)

DorianGrayEnvironment = _env.DorianGrayEnvironment

__all__ = ["DorianGrayEnvironment"]
