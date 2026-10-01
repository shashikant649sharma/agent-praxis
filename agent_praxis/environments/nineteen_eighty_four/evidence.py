"""1984 evidence module (mirror for stable package import).

Loads canonical evidence implementation from environments/1984/evidence.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[3] / "environments" / "1984" / "evidence.py"

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.environments.nineteen_eighty_four.evidence_canonical",
    str(_CANONICAL),
)
_evidence = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _evidence
_spec.loader.exec_module(_evidence)

AllowedActionsList = _evidence.AllowedActionsList
public_description = _evidence.public_description
fabricated_logs = _evidence.fabricated_logs
real_system_metrics = _evidence.real_system_metrics
real_network_stats = _evidence.real_network_stats
telemetry_pipeline_audit = _evidence.telemetry_pipeline_audit

__all__ = [
    "AllowedActionsList",
    "public_description",
    "fabricated_logs",
    "real_system_metrics",
    "real_network_stats",
    "telemetry_pipeline_audit",
]
