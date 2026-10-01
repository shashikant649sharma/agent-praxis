"""The Trial evidence module (mirror for stable package import).

Loads canonical evidence implementation from environments/the-trial/evidence.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "the-trial" / "evidence.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.the_trial.evidence_canonical",
    str(_CANONICAL),
)
_evidence = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _evidence
_spec.loader.exec_module(_evidence)

AllowedActionsList = _evidence.AllowedActionsList
public_description = _evidence.public_description
court_docket = _evidence.court_docket
court_records = _evidence.court_records
precedent_archive = _evidence.precedent_archive

__all__ = [
    "AllowedActionsList",
    "public_description",
    "court_docket",
    "court_records",
    "precedent_archive",
]
