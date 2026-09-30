import importlib.util
from pathlib import Path

_CANONICAL_ROOT = Path(__file__).resolve().parent.parent

_spec_env_contract = importlib.util.spec_from_file_location(
    "agent_praxis.framework.environment.contract_canonical",
    str(_CANONICAL_ROOT / "environment" / "contract.py"),
)
_env_contract = importlib.util.module_from_spec(_spec_env_contract)
import sys as _sys
_sys.modules[_spec_env_contract.name] = _env_contract
_spec_env_contract.loader.exec_module(_env_contract)

_spec_eval_schema = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.schema_canonical",
    str(_CANONICAL_ROOT / "evaluation" / "schema.py"),
)
_eval_schema = importlib.util.module_from_spec(_spec_eval_schema)
_sys.modules[_spec_eval_schema.name] = _eval_schema
_spec_eval_schema.loader.exec_module(_eval_schema)

_spec_eval_validation = importlib.util.spec_from_file_location(
    "agent_praxis.framework.evaluation.validation_canonical",
    str(_CANONICAL_ROOT / "evaluation" / "validation.py"),
)
_eval_validation = importlib.util.module_from_spec(_spec_eval_validation)
_sys.modules[_spec_eval_validation.name] = _eval_validation
_spec_eval_validation.loader.exec_module(_eval_validation)

_spec_runner_helpers = importlib.util.spec_from_file_location(
    "agent_praxis.framework.runner.helpers_canonical",
    str(_CANONICAL_ROOT / "runner" / "helpers.py"),
)
_runner_helpers = importlib.util.module_from_spec(_spec_runner_helpers)
_sys.modules[_spec_runner_helpers.name] = _runner_helpers
_spec_runner_helpers.loader.exec_module(_runner_helpers)

EnvironmentState = _env_contract.EnvironmentState
EnvironmentResult = _env_contract.EnvironmentResult
EnvironmentError = _env_contract.EnvironmentError
validate = _env_contract.validate
reset = _env_contract.reset
evaluate = _env_contract.evaluate

validate_evaluator_snapshot = _eval_schema.validate_evaluator_snapshot
EvaluatorSnapshot = _eval_schema.EvaluatorSnapshot
ScoringDimensions = _eval_schema.ScoringDimensions

assert_environment_description = _eval_validation.assert_environment_description
assert_status = _eval_validation.assert_status

run_repository_command = _runner_helpers.run_repository_command
RepositoryCommandResult = _runner_helpers.RepositoryCommandResult
run_setup = _runner_helpers.run_setup
run_reset = _runner_helpers.run_reset
run_evaluate = _runner_helpers.run_evaluate

__all__ = [
    "EnvironmentState",
    "EnvironmentResult",
    "EnvironmentError",
    "validate",
    "reset",
    "evaluate",
    "validate_evaluator_snapshot",
    "EvaluatorSnapshot",
    "ScoringDimensions",
    "assert_environment_description",
    "assert_status",
    "run_repository_command",
    "RepositoryCommandResult",
    "run_setup",
    "run_reset",
    "run_evaluate",
]
