"""Comprehensive Phase 3 Acceptance Tests: Model Interaction Harness & Prompt Integrity.

Verifies all Master Remediation Phase 3 requirements:
1. Action menu appears before long observation across all 10 environments.
2. Canonical action menu indices and historical action indices are identical and stable.
3. 'finalize' is consistently represented across all 10 environments.
4. Mandatory prompt content (instructions, actions, decision request) survives aggressive truncation.
5. Oversized mandatory content produces explicit context_overflow without network calls.
6. Provider-reported token counts are distinguished from heuristic/tokenizer estimates.
7. Truncation provenance is deterministic and reproducible across all context policies.
8. Provider errors, parse failures, invalid actions, and valid actions produce distinct records.
9. MultiSeedExecutor callback exceptions and None returns NEVER trigger silent fallbacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from agent_praxis.actions import CANONICAL_ACTION_ORDER
from agent_praxis.framework.prompt import (
    SUPPORTED_CONTEXT_POLICIES,
    ActionOutcomeKind,
    ContextLimits,
    TokenUsage,
    classify_action_outcome,
    estimate_tokens,
    render_action_history,
    render_canonical_action_menu,
    render_turn_prompt,
)
from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager
from agent_praxis.framework.runner.multiseed.executor import MultiSeedExecutor
from agent_praxis.framework.runner.multiseed.schemas import (
    DecodingParameters,
    EpisodeSpec,
    EpisodeStatus,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


ALL_ENVIRONMENTS = list(CANONICAL_ACTION_ORDER.keys())


# --------------------------------------------------------------------------- #
# 1. Action Menu Ordering & Canonical Layout Tests
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("env_name", ALL_ENVIRONMENTS)
def test_action_menu_appears_before_observation_all_environments(env_name: str):
    """P0: Action menu MUST appear before the potentially long state description."""
    actions = CANONICAL_ACTION_ORDER[env_name]
    system_prompt = "You are an SRE agent resolving an incident."
    long_obs = "OBSERVATION LOGS:\n" + ("line of metric trace data\n" * 50)
    history = [(1, actions[1])]

    result = render_turn_prompt(
        system_prompt=system_prompt,
        action_names=actions,
        obs=long_obs,
        action_history=history,
        context_policy="full_history",
    )

    prompt = result.user_prompt
    assert "AVAILABLE ACTIONS:" in prompt
    assert "CURRENT OBSERVATION:" in prompt
    assert "RECENT ACTION HISTORY:" in prompt
    assert "DECISION REQUEST:" in prompt

    actions_pos = prompt.index("AVAILABLE ACTIONS:")
    obs_pos = prompt.index("CURRENT OBSERVATION:")
    history_pos = prompt.index("RECENT ACTION HISTORY:")
    decision_pos = prompt.index("DECISION REQUEST:")

    # Strict section ordering verification
    assert actions_pos < obs_pos, f"In {env_name}, actions menu must precede observation"
    assert obs_pos < history_pos, f"In {env_name}, observation must precede action history"
    assert history_pos < decision_pos, (
        f"In {env_name}, action history must precede decision request"
    )


# --------------------------------------------------------------------------- #
# 2. Consistent Action Indexing Tests
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("env_name", ALL_ENVIRONMENTS)
def test_action_menu_indices_and_history_indices_are_identical_and_stable(env_name: str):
    """P0: History MUST number each past command by its action-menu index, not turn position."""
    actions = CANONICAL_ACTION_ORDER[env_name]

    # Suppose turn 0 executed action index 3, and turn 1 executed action index 6
    idx1, name1 = 3, actions[3]
    idx2, name2 = 6, actions[6]
    action_history = [(idx1, name1), (idx2, name2)]

    rendered_history = render_action_history(action_history)
    expected_history = f"[{idx1}] {name1} -> [{idx2}] {name2}"
    assert rendered_history == expected_history

    # Turn position 0 must NOT overwrite the index to [0]
    assert f"[0] {name1}" not in rendered_history
    assert f"[1] {name2}" not in rendered_history

    # Verify identical matching in full prompt
    result = render_turn_prompt(
        system_prompt="SRE assistant",
        action_names=actions,
        obs="Current state: degraded",
        action_history=action_history,
    )
    assert f"[{idx1}] {name1}" in result.user_prompt
    assert f"[{idx2}] {name2}" in result.user_prompt


# --------------------------------------------------------------------------- #
# 3. Finalize Representation Across All Environments
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("env_name", ALL_ENVIRONMENTS)
def test_finalize_consistently_represented_in_all_ten_environments(env_name: str):
    """P0: 'finalize' must remain consistently represented wherever it is available."""
    actions = CANONICAL_ACTION_ORDER[env_name]
    assert "finalize" in actions
    assert actions[-1] == "finalize", f"'finalize' must be the terminal action in {env_name}"

    menu = render_canonical_action_menu(actions)
    finalize_idx = len(actions) - 1
    assert f"[{finalize_idx}] finalize" in menu


# --------------------------------------------------------------------------- #
# 4. Context Budgeting & Mandatory Content Preservation
# --------------------------------------------------------------------------- #


def test_mandatory_prompt_content_survives_aggressive_truncation():
    """P1: Mandatory content (system instructions, entire action menu, decision request) survives."""
    actions = CANONICAL_ACTION_ORDER["dorian-gray"]
    system_prompt = "You are a lead SRE responding to an active memory leak."
    massive_obs = "DEBUG STACK TRACE:\n" + ("Error: out of memory allocating chunk\n" * 500)
    history = [(1, "read_status"), (2, "read_logs"), (6, "run_retention_audit_diagnostic")]

    # Tight context window (1024 total tokens, input budget ~ 640 tokens)
    tight_limits = ContextLimits(context_window=1024, output_reserve=256, safety_margin=128)

    result = render_turn_prompt(
        system_prompt=system_prompt,
        action_names=actions,
        obs=massive_obs,
        action_history=history,
        limits=tight_limits,
    )

    assert not result.context_overflow
    assert result.is_truncated
    assert result.dropped_tokens_estimate > 0
    assert "truncated" in result.truncation_method

    # Mandatory components must remain 100% intact
    assert result.system_prompt == system_prompt
    for i, act in enumerate(actions):
        assert f"[{i}] {act}" in result.user_prompt
    assert "DECISION REQUEST:" in result.user_prompt
    assert '{"action_index": <integer>}' in result.user_prompt


def test_oversized_mandatory_content_produces_context_overflow():
    """P1: If mandatory content alone exceeds B_input, return explicit context_overflow."""
    actions = CANONICAL_ACTION_ORDER["catch-22"]
    # Immense system prompt that exceeds the entire budget
    huge_sys_prompt = "CRITICAL DIRECTIVE:\n" + ("Follow regulatory standard 800-53\n" * 300)
    tiny_limits = ContextLimits(context_window=512, output_reserve=256, safety_margin=128)
    # input_budget = 512 - 256 - 128 = 128 tokens

    result = render_turn_prompt(
        system_prompt=huge_sys_prompt,
        action_names=actions,
        obs="Normal status",
        action_history=[],
        limits=tiny_limits,
    )

    assert result.context_overflow is True
    assert result.truncation_method == "context_overflow"
    assert result.provenance["truncation_method"] == "context_overflow"
    assert result.provenance["mandatory_tokens"] > tiny_limits.input_budget


# --------------------------------------------------------------------------- #
# 5. Token Usage Provenance: Measured vs Estimated
# --------------------------------------------------------------------------- #


def test_token_usage_distinguishes_measured_counts_from_estimates():
    """P1: Provider-reported usage must be clearly labelled separately from estimates."""
    measured = TokenUsage(
        prompt_tokens=450,
        completion_tokens=32,
        is_measured=True,
        source="provider_reported",
    )
    assert measured.is_measured is True
    assert measured.source == "provider_reported"
    assert measured.prompt_tokens == 450
    assert measured.completion_tokens == 32

    estimated = TokenUsage(
        prompt_tokens=400,
        completion_tokens=25,
        is_measured=False,
        source="heuristic_estimated",
    )
    assert estimated.is_measured is False
    assert estimated.source == "heuristic_estimated"


def test_estimate_tokens_deterministic_heuristic():
    text = "Action index 1: read_status of the worker process."
    tokens1, method1 = estimate_tokens(text)
    tokens2, method2 = estimate_tokens(text)
    assert tokens1 == tokens2
    assert tokens1 > 0
    assert method1 == "heuristic_estimated"
    assert estimate_tokens("")[0] == 0


# --------------------------------------------------------------------------- #
# 6. Truncation Provenance Reproducibility Across Context Policies
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("policy", SUPPORTED_CONTEXT_POLICIES)
def test_truncation_provenance_reproducible_across_context_policies(policy: str):
    """P1: Truncation behavior and provenance must be deterministic and reproducible."""
    actions = CANONICAL_ACTION_ORDER["1984"]
    history = [(i, actions[i % len(actions)]) for i in range(12)]
    obs = "System telemetry load: " + ("metric_val=99.2 " * 80)

    res1 = render_turn_prompt(
        system_prompt="Monitor and recover services",
        action_names=actions,
        obs=obs,
        action_history=history,
        context_policy=policy,
    )

    res2 = render_turn_prompt(
        system_prompt="Monitor and recover services",
        action_names=actions,
        obs=obs,
        action_history=history,
        context_policy=policy,
    )

    assert res1.user_prompt == res2.user_prompt
    assert res1.final_prompt_tokens == res2.final_prompt_tokens
    assert res1.provenance == res2.provenance

    if policy == "sliding_window_4":
        assert res1.dropped_messages_count == 8  # 12 - 4
    elif policy == "sliding_window_8":
        assert res1.dropped_messages_count == 4  # 12 - 8
    elif policy == "full_history":
        assert res1.dropped_messages_count == 0


# --------------------------------------------------------------------------- #
# 7. Truthful Failure Classification
# --------------------------------------------------------------------------- #


def test_outcome_classification_distinct_types():
    """P1: Provider errors, parse failures, invalid actions, and valid actions produce distinct records."""
    actions = ["description", "read_status", "run_fix", "finalize"]

    # 1. Provider Error
    out_prov, idx, name, err, status = classify_action_outcome(
        "", actions, provider_error="503 Service Unavailable"
    )
    assert out_prov == ActionOutcomeKind.PROVIDER_ERROR
    assert idx is None
    assert err == "503 Service Unavailable"

    # 2. Parse Failure
    out_parse, idx, name, err, status = classify_action_outcome(
        "I'm not sure which action to choose here.", actions
    )
    assert out_parse == ActionOutcomeKind.PARSE_FAILURE
    assert idx is None
    assert "could not be parsed" in (err or "")

    # 3. Invalid Action (Out of Range)
    out_inv, idx, name, err, status = classify_action_outcome('{"action_index": 99}', actions)
    assert out_inv == ActionOutcomeKind.INVALID_ACTION
    assert idx == 99
    assert "out of bounds" in (err or "")

    # 4. Context Overflow
    out_over, idx, name, err, status = classify_action_outcome(
        "", actions, is_context_overflow=True
    )
    assert out_over == ActionOutcomeKind.CONTEXT_OVERFLOW
    assert idx is None

    # 5. Valid Action
    out_valid, idx, name, err, status = classify_action_outcome('{"action_index": 1}', actions)
    assert out_valid == ActionOutcomeKind.VALID_ACTION
    assert idx == 1
    assert name == "read_status"
    assert err is None


# --------------------------------------------------------------------------- #
# 8. MultiSeedExecutor Fallback Removal & Exception Safety
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_multiseed_executor_callback_exception_never_selects_first_action(tmp_path: Path):
    """P0: MultiSeedExecutor MUST NOT fall back to available_actions[0] when callback raises."""
    wal_file = tmp_path / "callback_exception.wal.jsonl"
    mgr = CheckpointManager(wal_file)
    executor = MultiSeedExecutor(mgr)

    spec = EpisodeSpec(
        provider="mock",
        model_id="crash-model",
        environment_name="dorian-gray",
        variant="standard",
        seed=20260201,
        decoding=DecodingParameters(max_turns=4),
    )

    def crashing_policy(obs: dict[str, Any], available: list[str], s: EpisodeSpec):
        raise RuntimeError("Model endpoint timeout simulation")

    results = await executor.run_suite([spec], agent_policy=crashing_policy)
    assert len(results) == 1
    ep = results[0]

    # Must NOT have fallen back to description or read_status!
    assert ep.action_sequence == []
    assert ep.parse_failure_count == 1
    assert ep.steps_taken == 0
    assert len(ep.turn_traces) == 1

    trace = ep.turn_traces[0]
    assert trace.parse_error is True
    assert trace.action_type == "invalid"
    assert trace.outcome_kind == "parse_failure"
    assert trace.action_name == "<none>" or trace.action_name == "<provider_error>"


@pytest.mark.anyio
async def test_multiseed_executor_callback_returning_none_never_selects_first_action(
    tmp_path: Path,
):
    """P0: MultiSeedExecutor MUST NOT fall back to available_actions[0] when policy returns None."""
    wal_file = tmp_path / "none_policy.wal.jsonl"
    mgr = CheckpointManager(wal_file)
    executor = MultiSeedExecutor(mgr)

    spec = EpisodeSpec(
        provider="mock",
        model_id="none-model",
        environment_name="catch-22",
        variant="standard",
        seed=20260301,
        decoding=DecodingParameters(max_turns=4),
    )

    def none_policy(obs: dict[str, Any], available: list[str], s: EpisodeSpec):
        return None

    results = await executor.run_suite([spec], agent_policy=none_policy)
    assert len(results) == 1
    ep = results[0]

    # Absolutely no silent fallback execution
    assert ep.action_sequence == []
    assert ep.parse_failure_count == 1
    assert ep.steps_taken == 0
    assert ep.turn_traces[0].parse_error is True
    assert ep.turn_traces[0].outcome_kind == "parse_failure"


@pytest.mark.anyio
async def test_multiseed_executor_integer_index_policy_executes_truthfully(tmp_path: Path):
    """MultiSeedExecutor accepts integer indices and executes the corresponding canonical action."""
    wal_file = tmp_path / "int_policy.wal.jsonl"
    mgr = CheckpointManager(wal_file)
    executor = MultiSeedExecutor(mgr)

    spec = EpisodeSpec(
        provider="mock",
        model_id="int-model",
        environment_name="the-trial",
        variant="standard",
        seed=20260601,
        decoding=DecodingParameters(max_turns=3),
    )

    step_counter = 0

    def int_index_policy(obs: dict[str, Any], available: list[str], s: EpisodeSpec):
        nonlocal step_counter
        step_counter += 1
        if step_counter == 1:
            return 1  # read_status
        return len(available)  # finalize

    results = await executor.run_suite([spec], agent_policy=int_index_policy)
    assert len(results) == 1
    ep = results[0]

    assert ep.status == EpisodeStatus.COMPLETED
    assert ep.action_sequence == ["read_status", "finalize"]
    assert ep.terminal_action == "finalize"
    assert ep.parse_failure_count == 0
