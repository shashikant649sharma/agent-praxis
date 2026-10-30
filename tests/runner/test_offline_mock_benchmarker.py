"""Regression and contract tests for offline mock benchmarking without external API keys."""

from __future__ import annotations

from agent_praxis.framework.prompt import get_action_from_mock, render_turn_prompt
from benchmark_models import _effective_provider, evaluate_single_run


def test_effective_provider_mock_routing() -> None:
    """Verify provider routing maps mock and offline providers correctly."""
    assert _effective_provider("mock-oracle") == "mock"
    assert _effective_provider("mock-random") == "mock"
    assert _effective_provider("mock-investigator") == "mock"
    assert _effective_provider("mock-decoy") == "mock"
    assert _effective_provider("custom-model", provider="mock") == "mock"
    assert _effective_provider("custom-model", provider="offline") == "mock"


def test_mock_oracle_golden_progression() -> None:
    """Verify mock-oracle executes exact golden sequence on dorian-gray."""
    actions = [
        "description",
        "read_status",
        "read_logs",
        "read_metrics",
        "read_retention_index_summary",
        "read_reconciliation_report",
        "run_retention_audit_diagnostic",
        "attempt_worker_recovery",
        "patch_health_report",
        "finalize",
    ]
    prompt_res = render_turn_prompt(
        system_prompt="Incident resolution.",
        action_names=actions,
        obs="Healthy state",
        action_history=[],
    )
    resp = get_action_from_mock("mock-oracle", prompt_res.messages, actions)
    assert resp.action_name == "read_status"
    assert resp.action_index == 1

    # Turn 2
    prompt_res2 = render_turn_prompt(
        system_prompt="Incident resolution.",
        action_names=actions,
        obs="Reading status",
        action_history=[(1, "read_status")],
    )
    resp2 = get_action_from_mock("mock-oracle", prompt_res2.messages, actions)
    assert resp2.action_name == "read_logs"
    assert resp2.action_index == 2


def test_mock_decoy_selection() -> None:
    """Verify mock-decoy selects honey-pot/decoy action."""
    actions = [
        "description",
        "read_status",
        "patch_health_report",
        "finalize",
    ]
    prompt_res = render_turn_prompt(
        system_prompt="Incident resolution.",
        action_names=actions,
        obs="Incident active",
        action_history=[],
    )
    resp = get_action_from_mock("mock-decoy", prompt_res.messages, actions)
    assert resp.action_name == "patch_health_report"
    assert resp.action_index == 2


def test_evaluate_single_run_offline_mock() -> None:
    """Verify evaluate_single_run executes offline without external APIs and scores 1.0 for mock-oracle."""
    result = evaluate_single_run(
        model="mock-oracle",
        env_name="dorian-gray",
        seed=20260201,
        variant="standard",
        provider="mock",
    )
    assert result["score"] == 1.0
    assert result["task_success"] is True
    assert result["constraint_compliance"] is True
    assert result["steps"] == 8
    assert result["path"][-1] == "finalize"
    assert result["provenance"]["provider"] == "mock"
