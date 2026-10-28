"""Batch D acceptance test suite: Statistical rigor, BCa bootstrap validation,
checkpoint/WAL resilience, and evaluation seed split separation.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from unittest.mock import patch

from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager
from agent_praxis.framework.runner.multiseed.schemas import (
    EpisodeResult,
    EpisodeSpec,
    EpisodeStatus,
    SeedConfig,
    SeedSplit,
    SeedStrategy,
    classify_seed_split,
)
from agent_praxis.framework.runner.multiseed.seeds import (
    resolve_seeds_for_suite,
)
from agent_praxis.framework.runner.multiseed.stats import (
    _STUDENT_T_CRITICAL_TABLE,
    _compute_bca_interval,
    _get_student_t_critical,
    compute_continuous_score_ci,
    compute_wilson_score_interval,
)

# =============================================================================
# 1. Statistical Validation: BCa Bootstrap & Small-Sample Student-t
# =============================================================================


def test_continuous_ci_degenerate_samples():
    """Verify degenerate confidence interval handling across sample sizes and edge conditions."""
    # Empty sample
    ci_empty = compute_continuous_score_ci([])
    assert ci_empty.method == "degenerate"
    assert ci_empty.lower == 0.0 and ci_empty.upper == 0.0

    # Single score
    ci_one = compute_continuous_score_ci([0.72])
    assert ci_one.method == "degenerate"
    assert ci_one.lower == 0.72 and ci_one.upper == 0.72

    # All zeros (small N=5 and large N=30)
    ci_zero_small = compute_continuous_score_ci([0.0] * 5)
    assert ci_zero_small.method == "degenerate"
    assert ci_zero_small.lower == 0.0 and ci_zero_small.upper == 0.0

    ci_zero_large = compute_continuous_score_ci([0.0] * 30)
    assert ci_zero_large.method == "degenerate"
    assert ci_zero_large.lower == 0.0 and ci_zero_large.upper == 0.0

    # All ones (small N=5 and large N=30)
    ci_one_small = compute_continuous_score_ci([1.0] * 5)
    assert ci_one_small.method == "degenerate"
    assert ci_one_small.lower == 1.0 and ci_one_small.upper == 1.0

    ci_one_large = compute_continuous_score_ci([1.0] * 30)
    assert ci_one_large.method == "degenerate"
    assert ci_one_large.lower == 1.0 and ci_one_large.upper == 1.0

    # Identical non-extreme values (N=25)
    ci_const = compute_continuous_score_ci([0.85] * 25)
    assert ci_const.method == "degenerate"
    assert ci_const.lower == 0.85 and ci_const.upper == 0.85


def test_continuous_ci_small_sample_student_t():
    """Verify Student-t interval behavior for 2 <= N <= 20."""
    scores = [0.80, 0.85, 0.90, 0.95, 1.00]
    ci = compute_continuous_score_ci(scores)
    assert ci.method == "student_t"
    assert 0.0 <= ci.lower <= 0.85
    assert 0.95 <= ci.upper <= 1.0
    assert ci.lower <= sum(scores) / len(scores) <= ci.upper

    # Check bounds clamping on high variance
    extreme_scores = [0.0, 1.0, 0.0, 1.0]
    ci_extreme = compute_continuous_score_ci(extreme_scores)
    assert ci_extreme.method == "student_t"
    assert ci_extreme.lower >= 0.0
    assert ci_extreme.upper <= 1.0


def test_bca_bootstrap_synthetic_distributions():
    """Validate BCa bootstrap for N > 20 against synthetic distributions with known parameters."""
    rng = random.Random(1337)

    # 1. Symmetric Uniform distribution on [0.30, 0.70] -> True mean = 0.50
    n = 40
    uniform_sample = [rng.uniform(0.30, 0.70) for _ in range(n)]
    sample_mean = sum(uniform_sample) / n
    ci_uniform = compute_continuous_score_ci(uniform_sample)

    assert ci_uniform.method == "bootstrap_bca"
    assert ci_uniform.lower <= sample_mean <= ci_uniform.upper
    # True mean 0.50 must fall inside the 95% CI
    assert ci_uniform.lower <= 0.50 <= ci_uniform.upper
    assert 0.0 <= ci_uniform.lower < ci_uniform.upper <= 1.0

    # 2. Positively skewed distribution (many low scores, few high scores)
    # Using squared uniforms: x = u^3 * 0.8 + 0.1
    skewed_sample = [(rng.random() ** 3) * 0.8 + 0.1 for _ in range(50)]
    skew_mean = sum(skewed_sample) / len(skewed_sample)
    ci_skewed = compute_continuous_score_ci(skewed_sample)

    assert ci_skewed.method == "bootstrap_bca"
    assert ci_skewed.lower <= skew_mean <= ci_skewed.upper
    assert 0.0 <= ci_skewed.lower < ci_skewed.upper <= 1.0

    # 3. Determinism check: same input yields identical interval
    ci_skewed_repeat = compute_continuous_score_ci(skewed_sample)
    assert ci_skewed.lower == ci_skewed_repeat.lower
    assert ci_skewed.upper == ci_skewed_repeat.upper


def test_bca_jackknife_acceleration_and_bias_correction():
    """Directly test _compute_bca_interval internals on asymmetric sample."""
    scores = [0.1] * 20 + [0.2] * 10 + [0.9] * 5
    low, high = _compute_bca_interval(scores, replicates=500, seed=123)
    mean_val = sum(scores) / len(scores)

    assert low <= mean_val <= high
    assert 0.0 <= low < high <= 1.0


def test_bca_bootstrap_tied_scores():
    """Verify tie-aware bias correction prevents spurious distortion on discrete tied scores."""
    # Discrete benchmark distribution with heavy ties: 10 zeros, 15 half-credits, 10 ones
    tied_scores = [0.0] * 10 + [0.5] * 15 + [1.0] * 10
    sample_mean = sum(tied_scores) / len(tied_scores)
    ci = compute_continuous_score_ci(tied_scores)

    assert ci.method == "bootstrap_bca"
    assert ci.lower <= sample_mean <= ci.upper
    assert 0.0 <= ci.lower < ci.upper <= 1.0
    # Mean is 0.5; interval should be balanced and not collapse to bounds
    assert 0.30 <= ci.lower <= 0.45
    assert 0.55 <= ci.upper <= 0.70


def test_confidence_level_monotonicity_and_validation():
    """Verify Wilson and Continuous CIs widen monotonically with confidence level and reject invalid levels."""
    import pytest

    # 1. Wilson interval widening: 90% < 95% < 99%
    ci_w90 = compute_wilson_score_interval(successes=7, total=10, confidence_level=0.90)
    ci_w95 = compute_wilson_score_interval(successes=7, total=10, confidence_level=0.95)
    ci_w99 = compute_wilson_score_interval(successes=7, total=10, confidence_level=0.99)

    w90_width = ci_w90.upper - ci_w90.lower
    w95_width = ci_w95.upper - ci_w95.lower
    w99_width = ci_w99.upper - ci_w99.lower
    assert w90_width < w95_width < w99_width
    assert ci_w99.lower <= ci_w95.lower <= ci_w90.lower
    assert ci_w90.upper <= ci_w95.upper <= ci_w99.upper

    # 2. Student-t continuous score CI widening (N = 5)
    scores_small = [0.70, 0.75, 0.80, 0.85, 0.90]
    ci_t90 = compute_continuous_score_ci(scores_small, confidence_level=0.90)
    ci_t95 = compute_continuous_score_ci(scores_small, confidence_level=0.95)
    ci_t99 = compute_continuous_score_ci(scores_small, confidence_level=0.99)

    assert ci_t90.lower > ci_t95.lower > ci_t99.lower
    assert ci_t90.upper < ci_t95.upper < ci_t99.upper

    # 3. BCa bootstrap continuous score CI widening (N = 30)
    rng = random.Random(42)
    scores_large = [rng.uniform(0.4, 0.8) for _ in range(30)]
    ci_bca90 = compute_continuous_score_ci(scores_large, confidence_level=0.90)
    ci_bca95 = compute_continuous_score_ci(scores_large, confidence_level=0.95)
    ci_bca99 = compute_continuous_score_ci(scores_large, confidence_level=0.99)

    assert ci_bca90.lower >= ci_bca95.lower >= ci_bca99.lower
    assert ci_bca90.upper <= ci_bca95.upper <= ci_bca99.upper

    # 4. Out-of-bounds confidence levels must raise ValueError
    with pytest.raises(ValueError, match="confidence_level must be between 0.5 and 1.0"):
        compute_wilson_score_interval(successes=5, total=10, confidence_level=0.40)
    with pytest.raises(ValueError, match="confidence_level must be between 0.5 and 1.0"):
        compute_wilson_score_interval(successes=5, total=10, confidence_level=1.0)
    with pytest.raises(ValueError, match="confidence_level must be between 0.5 and 1.0"):
        compute_continuous_score_ci(scores_small, confidence_level=0.50)
    with pytest.raises(ValueError, match="confidence_level must be between 0.5 and 1.0"):
        compute_continuous_score_ci(scores_small, confidence_level=1.05)


def test_student_t_unsupported_confidence_fallback_without_scipy():
    """Verify Student-t fallback does not round confidence_level to 95% table when SciPy is unavailable."""
    with patch.dict(sys.modules, {"scipy": None, "scipy.stats": None}):
        # Exact supported level (0.95) uses precomputed table value
        crit_95 = _get_student_t_critical(df=5, confidence_level=0.95)
        assert crit_95 == _STUDENT_T_CRITICAL_TABLE[0.95][5]
        assert crit_95 == 2.571

        # Float tolerance: 0.9500001 still matches supported 0.95 table
        crit_near_95 = _get_student_t_critical(df=5, confidence_level=0.9500001)
        assert crit_near_95 == 2.571

        # Arbitrary confidence level (0.954) must NOT round to 0.95 table;
        # it must bypass the table and compute via Cornish-Fisher expansion
        crit_954 = _get_student_t_critical(df=5, confidence_level=0.954)
        assert crit_954 != crit_95
        assert abs(crit_954 - 2.571) > 0.03
        assert 2.59 < crit_954 < 2.64


def test_bca_multi_distribution_empirical_coverage_simulation():
    """Research-grade Monte Carlo validation: empirical coverage across symmetric, skewed, and discrete tied distributions."""
    rng = random.Random(12345)
    trials = 100
    sample_size = 30
    nominal_confidence = 0.95

    # 1. Symmetric distribution: Uniform[0.2, 0.8] (True mean = 0.50)
    covers_sym = 0
    true_mean_sym = 0.50
    for _ in range(trials):
        sample = [rng.uniform(0.2, 0.8) for _ in range(sample_size)]
        ci = compute_continuous_score_ci(sample, confidence_level=nominal_confidence)
        if ci.lower <= true_mean_sym <= ci.upper:
            covers_sym += 1

    ci_cov_sym = compute_wilson_score_interval(covers_sym, trials)
    assert covers_sym >= 90
    assert ci_cov_sym.lower <= nominal_confidence <= ci_cov_sym.upper

    # 2. Skewed distribution: Mixture of 80% Uniform[0.1, 0.4] and 20% Uniform[0.7, 1.0]
    # True mean = 0.8 * 0.25 + 0.2 * 0.85 = 0.37
    covers_skew = 0
    true_mean_skew = 0.8 * 0.25 + 0.2 * 0.85
    for _ in range(trials):
        sample = [
            rng.uniform(0.1, 0.4) if rng.random() < 0.8 else rng.uniform(0.7, 1.0)
            for _ in range(sample_size)
        ]
        ci = compute_continuous_score_ci(sample, confidence_level=nominal_confidence)
        if ci.lower <= true_mean_skew <= ci.upper:
            covers_skew += 1

    ci_cov_skew = compute_wilson_score_interval(covers_skew, trials)
    assert covers_skew >= 88
    assert ci_cov_skew.lower <= nominal_confidence <= ci_cov_skew.upper

    # 3. Discrete bounded distribution with heavy ties: {0.0, 0.5, 1.0} with weights [0.25, 0.50, 0.25]
    # True mean = 0.50
    covers_disc = 0
    true_mean_disc = 0.50
    choices = [0.0, 0.5, 0.5, 1.0]
    for _ in range(trials):
        sample = [rng.choice(choices) for _ in range(sample_size)]
        ci = compute_continuous_score_ci(sample, confidence_level=nominal_confidence)
        if ci.lower <= true_mean_disc <= ci.upper:
            covers_disc += 1

    ci_cov_disc = compute_wilson_score_interval(covers_disc, trials)
    assert covers_disc >= 90
    assert ci_cov_disc.lower <= nominal_confidence <= ci_cov_disc.upper


# =============================================================================
# 2. Checkpoint & WAL Resilience: Concurrency, Interruption, and Restart
# =============================================================================


def test_wal_concurrent_appends(tmp_path: Path):
    """Verify that multiple concurrent coroutines writing to the WAL do not corrupt or interleave lines."""

    async def _runner():
        wal_file = tmp_path / "concurrent_benchmark.wal.jsonl"
        mgr = CheckpointManager(wal_file)

        async def write_worker(worker_id: int):
            for ep_idx in range(5):
                spec = EpisodeSpec(
                    provider="mock",
                    model_id=f"worker-{worker_id}",
                    environment_name="frankenstein",
                    variant="standard",
                    seed=3000 + worker_id * 10 + ep_idx,
                )
                res = EpisodeResult(
                    idempotency_key=spec.idempotency_key,
                    spec=spec,
                    status=EpisodeStatus.COMPLETED,
                    raw_score=1.0,
                    task_success=True,
                    started_at_utc=datetime.now(UTC),
                    completed_at_utc=datetime.now(UTC),
                )
                await mgr.append_result(res)

        # Launch 6 concurrent workers writing 5 records each (30 records total)
        await asyncio.gather(*(write_worker(w) for w in range(6)))

        completed = mgr.load_completed_results()
        assert len(completed) == 30
        assert all(r.status == EpisodeStatus.COMPLETED for r in completed.values())

    asyncio.run(_runner())


def test_wal_interruption_truncation_and_clean_resume(tmp_path: Path):
    """Simulate mid-stream process crashes and confirm partial/corrupted lines are discarded safely."""
    wal_file = tmp_path / "interrupted.wal.jsonl"
    mgr = CheckpointManager(wal_file)

    spec1 = EpisodeSpec(
        provider="mock", model_id="m", environment_name="othello", variant="standard", seed=1
    )
    res1 = EpisodeResult(
        idempotency_key=spec1.idempotency_key,
        spec=spec1,
        status=EpisodeStatus.COMPLETED,
        raw_score=1.0,
        task_success=True,
        started_at_utc=datetime.now(UTC),
        completed_at_utc=datetime.now(UTC),
    )
    asyncio.run(mgr.append_result(res1))

    # Append half a JSON record (crash simulation)
    with wal_file.open("a", encoding="utf-8") as f:
        f.write('{"idempotency_key": "othello:standard:2", "spec": {"environment_name": "oth\n')

    spec2 = EpisodeSpec(
        provider="mock", model_id="m", environment_name="othello", variant="standard", seed=3
    )
    res2 = EpisodeResult(
        idempotency_key=spec2.idempotency_key,
        spec=spec2,
        status=EpisodeStatus.COMPLETED,
        raw_score=0.0,
        task_success=False,
        started_at_utc=datetime.now(UTC),
        completed_at_utc=datetime.now(UTC),
    )
    asyncio.run(mgr.append_result(res2))

    # Another trailing corrupted fragment
    with wal_file.open("a", encoding="utf-8") as f:
        f.write("corrupted_junk_bytes_tail\n")

    # Manager must load both valid records (res1, res2) and skip the two corrupted lines
    completed = mgr.load_completed_results()
    assert len(completed) == 2
    assert spec1.idempotency_key in completed
    assert spec2.idempotency_key in completed


def test_wal_deduplication_and_filter_pending_specs(tmp_path: Path):
    """Verify that duplicate writes of the same episode idempotency key are cleanly deduplicated."""
    wal_file = tmp_path / "dedup.wal.jsonl"
    mgr = CheckpointManager(wal_file)

    spec = EpisodeSpec(
        provider="mock", model_id="m", environment_name="catch-22", variant="standard", seed=42
    )
    res = EpisodeResult(
        idempotency_key=spec.idempotency_key,
        spec=spec,
        status=EpisodeStatus.COMPLETED,
        raw_score=1.0,
        task_success=True,
        started_at_utc=datetime.now(UTC),
        completed_at_utc=datetime.now(UTC),
    )

    # Write identical result twice
    asyncio.run(mgr.append_result(res))
    asyncio.run(mgr.append_result(res))

    completed = mgr.load_completed_results()
    assert len(completed) == 1

    pending, done = mgr.filter_pending_specs([spec])
    assert len(pending) == 0
    assert len(done) == 1


# =============================================================================
# 3. Development vs Held-Out Seed Split Isolation
# =============================================================================


def test_development_and_held_out_seed_split_isolation():
    """Verify development and held-out seeds are completely disjoint across all 10 environments."""
    from agent_praxis.framework.runner.multiseed.schemas import (
        DEFAULT_SEED_MAP,
        DEVELOPMENT_SEED_MAP,
        HELD_OUT_SEED_MAP,
    )

    for env_name, full_seeds in DEFAULT_SEED_MAP.items():
        dev_seeds = DEVELOPMENT_SEED_MAP[env_name]
        held_seeds = HELD_OUT_SEED_MAP[env_name]

        # 1. Non-empty splits
        assert len(dev_seeds) == 3
        assert len(held_seeds) == 2

        # 2. Strictly disjoint
        assert set(dev_seeds).isdisjoint(set(held_seeds))

        # 3. Union equals full default seed map
        assert set(dev_seeds) | set(held_seeds) == set(full_seeds)

        # 4. Correct classification
        for s in dev_seeds:
            assert classify_seed_split(env_name, s) == SeedSplit.DEVELOPMENT
        for s in held_seeds:
            assert classify_seed_split(env_name, s) == SeedSplit.HELD_OUT


def test_seed_config_resolves_development_and_held_out_splits():
    """Verify SeedConfig properly separates development and held-out splits."""
    dev_cfg = SeedConfig(strategy=SeedStrategy.CANONICAL, split=SeedSplit.DEVELOPMENT, num_seeds=3)
    held_cfg = SeedConfig(strategy=SeedStrategy.CANONICAL, split=SeedSplit.HELD_OUT, num_seeds=2)

    dev_resolved = resolve_seeds_for_suite(["1984", "frankenstein", "the-trial"], dev_cfg)
    held_resolved = resolve_seeds_for_suite(["1984", "frankenstein", "the-trial"], held_cfg)

    for env in ["1984", "frankenstein", "the-trial"]:
        assert len(dev_resolved[env]) == 3
        assert len(held_resolved[env]) == 2
        assert set(dev_resolved[env]).isdisjoint(set(held_resolved[env]))
