import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).parent

_spec = importlib.util.spec_from_file_location(
    "agent_praxis.framework.runner.helpers_canonical",
    str(_ROOT.parent / "runner" / "helpers.py"),
)
_canonical = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _canonical
_spec.loader.exec_module(_canonical)

run_repository_command = _canonical.run_repository_command
RepositoryCommandResult = _canonical.RepositoryCommandResult
run_setup = _canonical.run_setup
run_reset = _canonical.run_reset
run_evaluate = _canonical.run_evaluate

__all__ = [
    "run_repository_command",
    "RepositoryCommandResult",
    "run_setup",
    "run_reset",
    "run_evaluate",
]
