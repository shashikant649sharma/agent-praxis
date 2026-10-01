"""Metamorphosis environment wrapper (mirror for stable package import).

Loads canonical environment implementation from environments/metamorphosis/environment.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "metamorphosis" / "environment.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.metamorphosis.environment_canonical",
    str(_CANONICAL),
)
_env = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _env
_spec.loader.exec_module(_env)

MetamorphosisEnvironment = _env.MetamorphosisEnvironment

__all__ = ["MetamorphosisEnvironment"]
