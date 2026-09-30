"""Agent Praxis framework evaluation sub-package — loads canonical schema + validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL_DIR = Path(__file__).resolve().parents[3] / "framework" / "evaluation"

_spec_schema = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.schema_canonical",
    str(_CANONICAL_DIR / "schema.py"),
)
_schema_mod = importlib.util.module_from_spec(_spec_schema)
sys.modules[_spec_schema.name] = _schema_mod
_spec_schema.loader.exec_module(_schema_mod)

_spec_validation = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.validation_canonical",
    str(_CANONICAL_DIR / "validation.py"),
)
_validation_mod = importlib.util.module_from_spec(_spec_validation)
sys.modules[_spec_validation.name] = _validation_mod
_spec_validation.loader.exec_module(_validation_mod)

schema = _schema_mod
validation = _validation_mod

__all__ = ["schema", "validation"]
