import sys
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).parent

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.validation_canonical",
    str(_ROOT.parent / "evaluation" / "validation.py"),
)
_canonical = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _canonical
_spec.loader.exec_module(_canonical)

assert_environment_description = _canonical.assert_environment_description
assert_status = _canonical.assert_status

__all__ = ["assert_environment_description", "assert_status"]
