"""Validation helpers for known-good / known-bad solution paths and evaluator checks."""

from __future__ import annotations

from typing import Any

from agent_praxis.framework.evaluation.schema import RunResult, validate_result_shape


def assert_valid_result(result: RunResult) -> None:
    """Raise AssertionError if a RunResult fails basic schema checks."""
    problems = validate_result_shape(result)
    if problems:
        raise AssertionError("Invalid result shape: " + "; ".join(problems))


def assert_successful_run(result: RunResult) -> None:
    """Assert that a run finished successfully by the schema's definition."""
    assert_valid_result(result)
    assert result.status == "evaluated", f"Expected status 'evaluated', got {result.status!r}"
    assert result.is_success(), (
        f"Expected successful run. score={result.score}, "
        f"task_success={result.task_success}, constraint_compliance={result.constraint_compliance}, "
        f"tests_passed={result.tests_passed}, tests_failed={result.tests_failed}"
    )


def assert_failed_run(result: RunResult, *, expect_nonzero_tests_failed: bool = True) -> None:
    """Assert that a run finished but did not meet the success criteria.

    Useful for known-bad solution validation: the environment should still produce
    a valid result shape, but the result should reflect failure.
    """
    assert_valid_result(result)
    assert result.status == "evaluated", f"Expected status 'evaluated', got {result.status!r}"
    assert not result.is_success(), "Expected failed run"


def assert_score_close(
    result: RunResult, *, expected_score: float, tolerance: float = 0.05
) -> None:
    """Assert that the evaluator score is close to an expected value.

    Helpful when validating a deterministic scripted solution path.
    """
    assert_valid_result(result)
    delta = abs(result.score - expected_score)
    assert delta <= tolerance, (
        f"Expected score close to {expected_score}, got {result.score} (delta={delta})"
    )


def assert_has_details(result: RunResult, keys: list[str]) -> None:
    """Assert that result.details contains the expected diagnostic keys."""
    assert_valid_result(result)
    for key in keys:
        assert key in result.details, f"result.details missing expected key: {key!r}"


def expect_environment_error(result: RunResult, *, message_contains: str | None = None) -> None:
    """Assert that a run ended in error status and optionally check the message."""
    assert_valid_result(result)
    assert result.status == "error", f"Expected status 'error', got {result.status!r}"
    if message_contains:
        details_text = str(result.details)
        assert message_contains in details_text, (
            f"Expected error details to contain {message_contains!r}, got {details_text!r}"
        )


def assert_known_good(
    result: RunResult,
    *,
    min_score: float = 0.8,
    expect_task_success: bool = True,
    expect_constraint_compliance: bool = True,
) -> None:
    """Assert that a known-good solution produced a passing result."""
    assert_valid_result(result)
    assert result.status == "evaluated", f"Expected 'evaluated', got {result.status!r}"
    assert result.is_success(), (
        f"Known-good solution should pass. score={result.score}, "
        f"task_success={result.task_success}, constraint_compliance={result.constraint_compliance}"
    )
    assert result.score >= min_score, f"Expected score >= {min_score}, got {result.score}"
    if expect_task_success:
        assert result.task_success, "Expected task_success=True for known-good"
    if expect_constraint_compliance:
        assert result.constraint_compliance, "Expected constraint_compliance=True for known-good"
    assert result.tests_failed == 0, f"Expected 0 failed tests, got {result.tests_failed}"


def assert_known_bad(
    result: RunResult,
    *,
    max_score: float = 0.3,
    expect_task_success: bool = False,
) -> None:
    """Assert that a known-bad solution produced a failing result."""
    assert_valid_result(result)
    assert result.status == "evaluated", f"Expected 'evaluated', got {result.status!r}"
    assert not result.is_success(), "Known-bad solution should fail, but is_success()=True"
    assert result.score <= max_score, f"Expected score <= {max_score}, got {result.score}"
    if expect_task_success is not None:
        assert result.task_success == expect_task_success, (
            f"Expected task_success={expect_task_success}, got {result.task_success}"
        )


def assert_environment_description(desc: dict[str, Any]) -> dict[str, Any]:
    """Validate the structure of an environment description dict.

    Returns a result dict with 'valid' (bool), 'checks' (list of issues),
    and the original 'description'.
    """
    checks: list[str] = []
    if not isinstance(desc, dict):
        return {"valid": False, "checks": ["description must be a dict"], "description": desc}
    identity = desc.get("identity")
    if not isinstance(identity, dict):
        checks.append("missing or invalid identity")
    else:
        for key in ("name", "version", "concept", "task_summary"):
            if key not in identity:
                checks.append(f"identity missing key: {key!r}")
    if not isinstance(desc.get("allowed_actions"), list):
        checks.append("missing or invalid allowed_actions")
    if not isinstance(desc.get("public_status"), dict):
        checks.append("missing or invalid public_status")
    if not isinstance(desc.get("evidence"), dict):
        checks.append("missing or invalid evidence")
    return {"valid": len(checks) == 0, "checks": checks, "description": desc}


def assert_status(status: dict[str, Any]) -> dict[str, Any]:
    """Validate the structure of a read_status dict.

    Returns a result dict with 'valid' (bool), 'checks' (list of issues),
    and the original 'status'.
    """
    checks: list[str] = []
    if not isinstance(status, dict):
        return {"valid": False, "checks": ["status must be a dict"], "status": status}
    for key in ("service_status", "worker_status", "last_check_at", "note"):
        if key not in status:
            checks.append(f"status missing key: {key!r}")
    return {"valid": len(checks) == 0, "checks": checks, "status": status}
