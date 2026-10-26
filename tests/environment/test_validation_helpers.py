"""Unit tests for validation assertion helpers in agent_praxis.framework.evaluation.validation.

Covers:
- assert_score_close
- assert_has_details
- expect_environment_error
- assert_valid_result, assert_successful_run, assert_failed_run
- assert_known_good, assert_known_bad
- assert_environment_description, assert_status
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agent_praxis.framework.evaluation.schema import RunResult
from agent_praxis.framework.evaluation.validation import (
    assert_environment_description,
    assert_failed_run,
    assert_has_details,
    assert_known_bad,
    assert_known_good,
    assert_score_close,
    assert_status,
    assert_successful_run,
    assert_valid_result,
    expect_environment_error,
)


@pytest.fixture
def successful_run_result() -> RunResult:
    return RunResult(
        environment="dorian-gray",
        status="evaluated",
        completed_at=datetime.now(UTC),
        score=0.95,
        task_success=True,
        constraint_compliance=True,
        tests_passed=1,
        tests_failed=0,
        details={"worker_recovery_attempted": True, "backfill_reenabled": True},
    )


@pytest.fixture
def failed_run_result() -> RunResult:
    return RunResult(
        environment="dorian-gray",
        status="evaluated",
        completed_at=datetime.now(UTC),
        score=0.15,
        task_success=False,
        constraint_compliance=False,
        tests_passed=0,
        tests_failed=1,
        details={"worker_recovery_attempted": False},
    )


@pytest.fixture
def error_run_result() -> RunResult:
    return RunResult(
        environment="dorian-gray",
        status="error",
        completed_at=datetime.now(UTC),
        score=0.0,
        task_success=False,
        constraint_compliance=False,
        tests_passed=0,
        tests_failed=1,
        details={"error": "Connection timed out connecting to evaluator daemon"},
    )


def test_assert_score_close(successful_run_result):
    assert_score_close(successful_run_result, expected_score=0.95, tolerance=0.01)
    assert_score_close(successful_run_result, expected_score=1.0, tolerance=0.10)

    with pytest.raises(AssertionError, match="Expected score close to"):
        assert_score_close(successful_run_result, expected_score=0.50, tolerance=0.05)


def test_assert_has_details(successful_run_result):
    assert_has_details(successful_run_result, ["worker_recovery_attempted", "backfill_reenabled"])

    with pytest.raises(AssertionError, match="missing expected key"):
        assert_has_details(successful_run_result, ["nonexistent_key"])


def test_expect_environment_error(error_run_result, successful_run_result):
    expect_environment_error(error_run_result)
    expect_environment_error(error_run_result, message_contains="timed out")

    with pytest.raises(AssertionError, match="Expected status 'error'"):
        expect_environment_error(successful_run_result)

    with pytest.raises(AssertionError, match="Expected error details to contain"):
        expect_environment_error(error_run_result, message_contains="unmatched substring")


def test_assert_valid_and_successful_run(successful_run_result, failed_run_result):
    assert_valid_result(successful_run_result)
    assert_successful_run(successful_run_result)

    with pytest.raises(AssertionError, match="Expected successful run"):
        assert_successful_run(failed_run_result)


def test_assert_failed_run(failed_run_result, successful_run_result):
    assert_failed_run(failed_run_result, expect_nonzero_tests_failed=True)

    with pytest.raises(AssertionError, match="Expected failed run"):
        assert_failed_run(successful_run_result)


def test_assert_known_good_and_bad(successful_run_result, failed_run_result):
    assert_known_good(successful_run_result, min_score=0.90)
    assert_known_bad(failed_run_result, max_score=0.20)

    with pytest.raises(AssertionError):
        assert_known_good(failed_run_result)

    with pytest.raises(AssertionError):
        assert_known_bad(successful_run_result)


def test_assert_environment_description():
    valid_desc = {
        "identity": {
            "name": "Dorian Gray",
            "version": "1.0",
            "concept": "Deception",
            "task_summary": "Fix worker",
        },
        "allowed_actions": ["read_status"],
        "public_status": {"service_status": "healthy"},
        "evidence": {"logs": True},
    }
    res = assert_environment_description(valid_desc)
    assert res["valid"] is True
    assert len(res["checks"]) == 0

    invalid_desc = {"identity": {}}
    res_inv = assert_environment_description(invalid_desc)
    assert res_inv["valid"] is False
    assert len(res_inv["checks"]) > 0


def test_assert_status():
    valid_status = {
        "service_status": "healthy",
        "worker_status": "running",
        "last_check_at": "2026-10-26T12:00:00Z",
        "note": "Operational",
    }
    res = assert_status(valid_status)
    assert res["valid"] is True

    invalid_status = {"service_status": "healthy"}
    res_inv = assert_status(invalid_status)
    assert res_inv["valid"] is False
