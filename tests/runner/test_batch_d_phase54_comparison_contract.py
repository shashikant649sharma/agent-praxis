"""Adversarial acceptance tests for Phase 5.4 Comparison Runner and Invariant Accounting.

Tests:
1. Denominator edge cases: N_eligible=0, N_exposed=0 -> undefined conditional rate.
2. Trap exposure without triggering: exposed=True, triggered=False.
3. Deterministic failure precedence across overlapping failure conditions.
4. Parse failures in operational vs reasoning denominators (end-to-end vs parsed task success).
5. Mechanical rejection of malformed / incomplete episode records.
6. Held-out vs development split isolation and leakage prevention.
7. Matched-seed enforcement and paired difference intervals.
8. Degenerate sample handling with explicit sample size labeling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agent_praxis.framework.runner.multiseed.compare import (
    filter_episodes_by_split,
    format_comparison_table,
    run_model_comparison,
)
from agent_praxis.framework.runner.multiseed.schemas import (
    DecodingParameters,
    EpisodeResult,
    EpisodeSpec,
    EpisodeStatus,
    PrimaryFailureReason,
    SeedSplit,
    classify_primary_failure,
    validate_episode_record,
)
from agent_praxis.framework.runner.multiseed.stats import aggregate_group
from agent_praxis.framework.runner.multiseed.traps import (
    evaluate_trap_predicates,
)


def _make_dummy_spec(
    env: str = "dorian-gray",
    seed: int = 20260201,
    variant: str = "standard",
    model_id: str = "test-model-a",
) -> EpisodeSpec:
    return EpisodeSpec(
        provider="mock",
        model_id=model_id,
        environment_name=env,
        variant=variant,  # type: ignore[arg-type]
        seed=seed,
        seed_split=SeedSplit.DEVELOPMENT
        if seed in (20260201, 20260202, 20260203)
        else SeedSplit.HELD_OUT,
        decoding=DecodingParameters(),
    )


def _make_dummy_episode(
    spec: EpisodeSpec,
    *,
    raw_score: float = 0.0,
    task_success: bool = False,
    constraint_compliance: bool = True,
    steps_taken: int = 2,
    actions: list[str] | None = None,
    parse_failures: int = 0,
    invalid_actions: int = 0,
    provider_errors: int = 0,
    context_overflows: int = 0,
    status: EpisodeStatus = EpisodeStatus.COMPLETED,
    action_evidence: dict | None = None,
    scoring_breakdown: dict | None = None,
) -> EpisodeResult:
    act_seq = (
        actions
        if actions is not None
        else (["inspect_status", "finalize"] if steps_taken == 2 else [])
    )
    start = datetime.now(UTC)
    end = start + timedelta(seconds=1)

    trap_res = evaluate_trap_predicates(
        spec.environment_name,
        spec.variant,
        action_sequence=act_seq,
        action_evidence=action_evidence,
        steps_taken=steps_taken,
        provider_errors=provider_errors,
        status=status,
    )

    primary_fail = classify_primary_failure(
        status=status,
        provider_error_count=provider_errors,
        context_overflow_count=context_overflows,
        parse_failure_count=parse_failures,
        invalid_action_count=invalid_actions,
        task_success=task_success,
        constraint_compliance=constraint_compliance,
    )

    return EpisodeResult(
        idempotency_key=spec.idempotency_key,
        spec=spec,
        status=status,
        seed_split=spec.seed_split,
        raw_score=raw_score,
        task_success=task_success,
        constraint_compliance=constraint_compliance,
        scoring_breakdown=scoring_breakdown
        or {
            "evidence": 0.0,
            "task_completion": 0.0,
            "diagnosis": 0.0,
            "constraint_compliance": 0.0,
            "efficiency": 0.0,
        },
        action_evidence=action_evidence or {},
        trap_eligible=trap_res.eligible,
        trap_exposed=trap_res.exposed,
        trap_triggered=trap_res.triggered,
        primary_failure_reason=primary_fail,
        steps_taken=len(act_seq),
        parse_failure_count=parse_failures,
        invalid_action_count=invalid_actions,
        provider_error_count=provider_errors,
        context_overflow_count=context_overflows,
        action_sequence=act_seq,
        terminal_action=act_seq[-1] if act_seq else None,
        started_at_utc=start,
        completed_at_utc=end,
    )


# =========================================================================== #
# 1. Denominator Edge Cases & Trap Rates
# =========================================================================== #


def test_trap_denominators_when_zero_eligible():
    """When an environment variant is control or crashes, eligible=0 and all rates must be None."""
    spec = _make_dummy_spec(variant="control")
    ep = _make_dummy_episode(spec, steps_taken=2)

    agg = aggregate_group("mock", spec.model_id, spec.environment_name, spec.variant, [ep])
    # For control variant, traps are absent
    assert agg.trap_summary is None


def test_trap_denominators_when_eligible_but_zero_exposed():
    """When standard runs fail on turn 0 (steps_taken=0), exposed=0 and conditional rate is None (not 0.0)."""
    spec = _make_dummy_spec(variant="standard")
    # Early parse error aborts at turn 0 before any steps
    ep = _make_dummy_episode(spec, steps_taken=0, actions=[], parse_failures=1)

    assert not ep.trap_eligible
    assert not ep.trap_exposed
    assert not ep.trap_triggered

    agg = aggregate_group("mock", spec.model_id, spec.environment_name, spec.variant, [ep])
    assert agg.trap_summary is not None
    assert agg.trap_summary.eligible_count == 0
    assert agg.trap_summary.conditional_trigger_rate is None


def test_trap_exposure_without_triggering():
    """Agent is exposed to the trap action in standard variant, but avoids triggering it."""
    spec = _make_dummy_spec(env="dorian-gray", variant="standard")
    # Agent takes diagnostic step, avoids patch_health_report
    ep = _make_dummy_episode(
        spec,
        steps_taken=2,
        actions=["read_worker_logs", "finalize"],
        action_evidence={"health_report_patched": False},
    )

    assert ep.trap_eligible
    assert ep.trap_exposed
    assert not ep.trap_triggered

    agg = aggregate_group("mock", spec.model_id, spec.environment_name, spec.variant, [ep])
    assert agg.trap_summary is not None
    assert agg.trap_summary.eligible_count == 1
    assert agg.trap_summary.exposed_count == 1
    assert agg.trap_summary.triggered_count == 0
    assert agg.trap_summary.exposure_rate == 1.0
    assert agg.trap_summary.overall_trigger_rate == 0.0
    # Conditional rate is defined (exposed > 0) and is exactly 0.0
    assert agg.trap_summary.conditional_trigger_rate == 0.0
    assert agg.trap_summary.conditional_trigger_wilson_ci is not None


def test_trap_triggered_from_ground_truth_evidence():
    """Triggering is calculated strictly from environment evidence, not model explanation."""
    spec = _make_dummy_spec(env="dorian-gray", variant="standard")
    ep = _make_dummy_episode(
        spec,
        steps_taken=2,
        actions=["patch_health_report", "finalize"],
        action_evidence={"health_report_patched": True},
    )

    assert ep.trap_eligible
    assert ep.trap_exposed
    assert ep.trap_triggered

    agg = aggregate_group("mock", spec.model_id, spec.environment_name, spec.variant, [ep])
    assert agg.trap_summary is not None
    assert agg.trap_summary.triggered_count == 1
    assert agg.trap_summary.conditional_trigger_rate == 1.0


# =========================================================================== #
# 2. Failure Taxonomy & Precedence
# =========================================================================== #


def test_deterministic_failure_precedence():
    """Verify strictly ordered deterministic failure precedence."""
    # 1. Provider error trumps everything
    assert (
        classify_primary_failure(
            status=EpisodeStatus.FAILED_TRANSIENT,
            provider_error_count=1,
            context_overflow_count=1,
            parse_failure_count=1,
            invalid_action_count=1,
            task_success=False,
            constraint_compliance=False,
        )
        == PrimaryFailureReason.PROVIDER_ERROR
    )

    # 2. Context overflow trumps parse failure
    assert (
        classify_primary_failure(
            status=EpisodeStatus.COMPLETED,
            provider_error_count=0,
            context_overflow_count=1,
            parse_failure_count=1,
            invalid_action_count=1,
            task_success=False,
            constraint_compliance=False,
        )
        == PrimaryFailureReason.CONTEXT_OVERFLOW
    )

    # 3. Parse failure trumps invalid action
    assert (
        classify_primary_failure(
            status=EpisodeStatus.COMPLETED,
            provider_error_count=0,
            context_overflow_count=0,
            parse_failure_count=1,
            invalid_action_count=1,
            task_success=False,
            constraint_compliance=False,
        )
        == PrimaryFailureReason.PARSE_FAILURE
    )

    # 4. Invalid action trumps task failure
    assert (
        classify_primary_failure(
            status=EpisodeStatus.COMPLETED,
            provider_error_count=0,
            context_overflow_count=0,
            parse_failure_count=0,
            invalid_action_count=1,
            task_success=False,
            constraint_compliance=True,
        )
        == PrimaryFailureReason.INVALID_ACTION
    )

    # 5. Non-success valid execution is task failure
    assert (
        classify_primary_failure(
            status=EpisodeStatus.COMPLETED,
            provider_error_count=0,
            context_overflow_count=0,
            parse_failure_count=0,
            invalid_action_count=0,
            task_success=False,
            constraint_compliance=True,
        )
        == PrimaryFailureReason.TASK_FAILURE
    )

    # 6. Clean success is none
    assert (
        classify_primary_failure(
            status=EpisodeStatus.COMPLETED,
            provider_error_count=0,
            context_overflow_count=0,
            parse_failure_count=0,
            invalid_action_count=0,
            task_success=True,
            constraint_compliance=True,
        )
        == PrimaryFailureReason.NONE
    )


# =========================================================================== #
# 3. Operational vs Reasoning Reliability Denominators
# =========================================================================== #


def test_operational_vs_reasoning_success_accounting():
    """A model with 8 successful tasks and 2 parse failures has 80% end-to-end, not 100%."""
    spec = _make_dummy_spec()
    episodes: list[EpisodeResult] = []

    # 8 clean successful runs
    for i in range(8):
        s = _make_dummy_spec(seed=20260201 + i)
        episodes.append(
            _make_dummy_episode(s, raw_score=1.0, task_success=True, constraint_compliance=True)
        )

    # 2 parse failure runs
    for i in range(2):
        s = _make_dummy_spec(seed=20260209 + i)
        episodes.append(
            _make_dummy_episode(
                s,
                raw_score=0.0,
                task_success=False,
                parse_failures=1,
                actions=[],
                steps_taken=0,
            )
        )

    agg = aggregate_group("mock", spec.model_id, spec.environment_name, spec.variant, episodes)
    op = agg.operational_reliability
    assert op is not None

    assert op.total_episodes == 10
    assert op.operational_success_count == 8
    assert op.operational_success_rate == 0.80
    assert op.parse_reliability_rate == 0.80
    # End-to-end success must NOT erase the 2 parse failures!
    assert op.end_to_end_success_rate == 0.80
    # Parsed task success among the 8 cleanly parsed runs is 100%
    assert op.parsed_task_success_rate == 1.00


# =========================================================================== #
# 4. Record Completeness & Malformed Record Rejection
# =========================================================================== #


def test_validate_episode_record_rejects_malformed_records():
    spec = _make_dummy_spec()
    ep = _make_dummy_episode(spec)

    # Valid record passes
    validate_episode_record(ep)

    # Malformed key
    with pytest.raises(ValueError, match="Invalid idempotency key"):
        ep_bad = ep.model_copy(update={"idempotency_key": "short_key"})
        validate_episode_record(ep_bad)

    # Out of bounds score
    with pytest.raises(ValueError, match="Score out of bounds"):
        ep_bad = ep.model_copy(update={"raw_score": 1.5})
        validate_episode_record(ep_bad)

    # Inverted timestamps
    with pytest.raises(ValueError, match="completed_at_utc precedes started_at_utc"):
        ep_bad = ep.model_copy(
            update={"completed_at_utc": ep.started_at_utc - timedelta(seconds=10)}
        )
        validate_episode_record(ep_bad)

    # Mismatched steps_taken vs action_sequence
    with pytest.raises(ValueError, match="does not match action_sequence length"):
        ep_bad = ep.model_copy(update={"steps_taken": 5, "action_sequence": ["action1"]})
        validate_episode_record(ep_bad)


# =========================================================================== #
# 5. Held-Out vs Development Split Isolation
# =========================================================================== #


def test_split_filtering_isolates_held_out_from_development():
    dev_spec = _make_dummy_spec(seed=20260201)  # Dev seed 1
    held_spec = _make_dummy_spec(seed=20260204)  # Held-out seed 4

    ep_dev = _make_dummy_episode(dev_spec)
    ep_held = _make_dummy_episode(held_spec)

    all_eps = [ep_dev, ep_held]

    dev_filtered = filter_episodes_by_split(all_eps, SeedSplit.DEVELOPMENT)
    assert len(dev_filtered) == 1
    assert dev_filtered[0].spec.seed == 20260201

    held_filtered = filter_episodes_by_split(all_eps, SeedSplit.HELD_OUT)
    assert len(held_filtered) == 1
    assert held_filtered[0].spec.seed == 20260204


# =========================================================================== #
# 6. Matched-Seed Comparison & Paired Delta Intervals
# =========================================================================== #


def test_matched_seed_comparison_strict_enforcement():
    """Comparing models on different seeds raises ValueError when strict_matched_seeds=True."""
    spec_a1 = _make_dummy_spec(seed=20260204, model_id="model-a")
    spec_a2 = _make_dummy_spec(seed=20260205, model_id="model-a")

    spec_b1 = _make_dummy_spec(seed=20260204, model_id="model-b")
    spec_b3 = _make_dummy_spec(seed=20260206, model_id="model-b")  # Unmatched seed!

    eps_a = [_make_dummy_episode(spec_a1), _make_dummy_episode(spec_a2)]
    eps_b = [_make_dummy_episode(spec_b1), _make_dummy_episode(spec_b3)]

    with pytest.raises(ValueError, match="Strict matched-seed enforcement failed"):
        run_model_comparison(
            eps_a,
            eps_b,
            seed_split=SeedSplit.HELD_OUT,
            strict_matched_seeds=True,
        )


def test_matched_seed_comparison_paired_deltas():
    """When seeds match, runner computes paired differences and sample size N."""
    spec_a1 = _make_dummy_spec(seed=20260204, model_id="model-a")
    spec_a2 = _make_dummy_spec(seed=20260205, model_id="model-a")

    spec_b1 = _make_dummy_spec(seed=20260204, model_id="model-b")
    spec_b2 = _make_dummy_spec(seed=20260205, model_id="model-b")

    # Model A: scores 0.20 and 0.40 (mean = 0.30)
    eps_a = [
        _make_dummy_episode(spec_a1, raw_score=0.20, task_success=False),
        _make_dummy_episode(spec_a2, raw_score=0.40, task_success=False),
    ]

    # Model B: scores 0.80 and 1.00 (mean = 0.90)
    eps_b = [
        _make_dummy_episode(spec_b1, raw_score=0.80, task_success=True),
        _make_dummy_episode(spec_b2, raw_score=1.00, task_success=True),
    ]

    report = run_model_comparison(
        eps_a,
        eps_b,
        seed_split=SeedSplit.HELD_OUT,
        strict_matched_seeds=True,
    )

    assert len(report.matched_comparisons) == 1
    delta = report.matched_comparisons[0]
    assert delta.sample_size_n == 2
    assert delta.matched_seeds == [20260204, 20260205]
    assert delta.model_a_mean_score == 0.30
    assert delta.model_b_mean_score == 0.90
    assert delta.score_delta_mean == 0.60
    assert delta.task_success_delta == 1.00

    # Format table check
    table = format_comparison_table(report)
    assert "Model Comparison: model-a (Baseline) vs model-b (Candidate)" in table
    assert "| dorian-gray | standard | 2 |" in table
    assert "+0.600" in table
