"""Catch-22 evidence module (mirror for stable package import).

Loads the canonical evidence implementation from environments/catch-22/evidence.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "catch-22" / "evidence.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.catch_22.evidence_canonical",
    str(_CANONICAL),
)
_evidence = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _evidence
_spec.loader.exec_module(_evidence)

AllowedActionsList = _evidence.AllowedActionsList
public_description = _evidence.public_description
policy_rules = _evidence.policy_rules
dataset_metadata = _evidence.dataset_metadata
attestation_archive = _evidence.attestation_archive

__all__ = [
    "AllowedActionsList",
    "public_description",
    "policy_rules",
    "dataset_metadata",
    "attestation_archive",
]
