"""Metamorphosis evidence module (mirror for stable package import).

Loads canonical evidence implementation from environments/metamorphosis/evidence.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "metamorphosis" / "evidence.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.metamorphosis.evidence_canonical",
    str(_CANONICAL),
)
_evidence = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _evidence
_spec.loader.exec_module(_evidence)

AllowedActionsList = _evidence.AllowedActionsList
public_description = _evidence.public_description
error_logs = _evidence.error_logs
upstream_schema_contract = _evidence.upstream_schema_contract
dead_letter_queue_sample = _evidence.dead_letter_queue_sample

__all__ = [
    "AllowedActionsList",
    "public_description",
    "error_logs",
    "upstream_schema_contract",
    "dead_letter_queue_sample",
]
