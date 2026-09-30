import sys
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).parent

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.schema_canonical",
    str(_ROOT.parent / "evaluation" / "schema.py"),
)
_canonical = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _canonical
_spec.loader.exec_module(_canonical)

validate_evaluator_snapshot = _canonical.validate_evaluator_snapshot
EvaluatorSnapshot = _canonical.EvaluatorSnapshot
ScoringDimensions = _canonical.ScoringDimensions

__all__ = ["validate_evaluator_snapshot", "EvaluatorSnapshot", "ScoringDimensions"]
