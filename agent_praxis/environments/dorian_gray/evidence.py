"""Dorian Gray evidence module (mirror for stable package import).

Loads the canonical evidence implementation from environments/dorian-gray/evidence.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "dorian-gray" / "evidence.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.dorian_gray.evidence_canonical",
    str(_CANONICAL),
)
_evidence = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _evidence
_spec.loader.exec_module(_evidence)

public_description = _evidence.public_description

__all__ = ["public_description"]
