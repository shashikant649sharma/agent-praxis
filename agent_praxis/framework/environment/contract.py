import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).parent

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.environment.contract_canonical",
    str(_ROOT.parent / "environment" / "contract.py"),
)
_canonical = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _canonical
_spec.loader.exec_module(_canonical)

EnvironmentState = _canonical.EnvironmentState
EnvironmentResult = _canonical.EnvironmentResult
EnvironmentError = _canonical.EnvironmentError
validate = _canonical.validate
reset = _canonical.reset
evaluate = _canonical.evaluate

__all__ = [
    "EnvironmentState",
    "EnvironmentResult",
    "EnvironmentError",
    "validate",
    "reset",
    "evaluate",
]
