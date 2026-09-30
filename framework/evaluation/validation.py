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
    assert (
        result.status == "evaluated"
    ), f"Expected status 'evaluated', got {result.status!r}"
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


def assert_score_close(result: RunResult, *, expected_score: float, tolerance: float = 0.05) -> None:
    """Assert that the evaluator score is close to an expected value.

    Helpful when validating a deterministic scripted solution path.
    """
    assert_valid_result(result)
    delta = abs(result.score - expected_score)
    assert delta <= tolerance, f"Expected score close to {expected_score}, got {result.score} (delta={delta})"


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
