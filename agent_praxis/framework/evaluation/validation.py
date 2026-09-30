import sys
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.validation_canonical",
    str(_ROOT / "framework" / "evaluation" / "validation.py"),
)
_canonical = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _canonical
_spec.loader.exec_module(_canonical)

assert_valid_result = _canonical.assert_valid_result
assert_successful_run = _canonical.assert_successful_run
assert_failed_run = _canonical.assert_failed_run
assert_score_close = _canonical.assert_score_close
assert_has_details = _canonical.assert_has_details
expect_environment_error = _canonical.expect_environment_error

__all__ = [
    "assert_valid_result",
    "assert_successful_run",
    "assert_failed_run",
    "assert_score_close",
    "assert_has_details",
    "expect_environment_error",
]
