import sys
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.schema_canonical",
    str(_ROOT / "framework" / "evaluation" / "schema.py"),
)
_canonical = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _canonical
_spec.loader.exec_module(_canonical)

RunResult = _canonical.RunResult
validate_result_shape = _canonical.validate_result_shape

__all__ = [
    "RunResult",
    "validate_result_shape",
    "make_run_result",
]
