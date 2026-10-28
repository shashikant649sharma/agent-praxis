"""Statistical aggregation engine for multi-seed benchmark evaluations.

Implements small-sample Wilson score intervals, Student-t confidence intervals,
bootstrap resamplers, and behavioral consistency metrics.
"""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter

from agent_praxis.framework.runner.multiseed.schemas import (
    ConfidenceInterval,
    EpisodeResult,
    EpisodeStatus,
    MultiSeedAggregateResult,
    OperationalReliabilitySummary,
    PrimaryFailureBreakdown,
    PrimaryFailureReason,
    TrapRateSummary,
)
from agent_praxis.framework.runner.multiseed.traps import compute_trap_rates

# Two-tailed t critical values for degrees of freedom 1..20 at standard confidence levels
_STUDENT_T_CRITICAL_TABLE: dict[float, dict[int, float]] = {
    0.90: {
        1: 6.314,
        2: 2.920,
        3: 2.353,
        4: 2.132,
        5: 2.015,
        6: 1.943,
        7: 1.895,
        8: 1.860,
        9: 1.833,
        10: 1.812,
        11: 1.796,
        12: 1.782,
        13: 1.771,
        14: 1.761,
        15: 1.753,
        16: 1.746,
        17: 1.740,
        18: 1.734,
        19: 1.729,
        20: 1.725,
    },
    0.95: {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        11: 2.201,
        12: 2.179,
        13: 2.160,
        14: 2.145,
        15: 2.131,
        16: 2.120,
        17: 2.110,
        18: 2.101,
        19: 2.093,
        20: 2.086,
    },
    0.99: {
        1: 63.657,
        2: 9.925,
        3: 5.841,
        4: 4.604,
        5: 4.032,
        6: 3.707,
        7: 3.499,
        8: 3.355,
        9: 3.250,
        10: 3.169,
        11: 3.106,
        12: 3.055,
        13: 3.012,
        14: 2.977,
        15: 2.947,
        16: 2.921,
        17: 2.898,
        18: 2.878,
        19: 2.861,
        20: 2.845,
    },
}
_STUDENT_T_CRITICAL_95: dict[int, float] = _STUDENT_T_CRITICAL_TABLE[0.95]


def _get_student_t_critical(df: int, confidence_level: float = 0.95) -> float:
    """Resolve two-tailed Student-t critical value for degrees of freedom df and confidence_level."""
    if df < 1:
        raise ValueError(f"Degrees of freedom must be >= 1, got {df}")
    if not (0.5 < confidence_level < 1.0):
        raise ValueError(f"confidence_level must be between 0.5 and 1.0, got {confidence_level}")

    # 1. Use scipy if available
    try:
        from scipy.stats import t  # type: ignore[import-untyped]

        alpha = 1.0 - confidence_level
        return float(t.ppf(1.0 - alpha / 2.0, df=df))
    except ImportError:
        pass

    # 2. Check precomputed exact tables for standard confidence levels (exact within float tolerance)
    for supported_level, table in _STUDENT_T_CRITICAL_TABLE.items():
        if abs(confidence_level - supported_level) < 1e-6 and df in table:
            return table[df]

    # 3. Accurate Cornish-Fisher expansion fallback for general confidence levels
    norm = statistics.NormalDist()
    z = norm.inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    term1 = z
    term2 = (z**3 + z) / (4.0 * df)
    term3 = (5.0 * (z**5) + 16.0 * (z**3) + 3.0 * z) / (96.0 * (df**2))
    return float(term1 + term2 + term3)


def compute_wilson_score_interval(
    successes: int,
    total: int,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute the Wilson score interval for a binomial proportion.

    Accurate even for small N or extreme proportions (e.g. 0% or 100% success).
    Dynamically honors requested confidence_level in (0.5, 1.0).
    """
    if not (0.5 < confidence_level < 1.0):
        raise ValueError(f"confidence_level must be between 0.5 and 1.0, got {confidence_level}")

    if total <= 0:
        return ConfidenceInterval(
            lower=0.0, upper=0.0, confidence_level=confidence_level, method="degenerate"
        )

    norm = statistics.NormalDist()
    z = norm.inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    p_hat = successes / total
    denom = 1.0 + (z**2) / total
    center = (p_hat + (z**2) / (2.0 * total)) / denom
    spread = (z * math.sqrt((p_hat * (1.0 - p_hat) / total) + (z**2) / (4.0 * (total**2)))) / denom

    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return ConfidenceInterval(
        lower=round(lower, 4),
        upper=round(upper, 4),
        confidence_level=confidence_level,
        method="wilson",
    )


def _compute_bca_interval(
    scores: list[float],
    confidence_level: float = 0.95,
    replicates: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute Bias-Corrected and Accelerated (BCa) bootstrap interval for sample mean.

    Uses tie-aware proportion: p_hat = (N_< + 0.5 * N_=) / B to prevent spurious bias
    inflation on discrete and bounded score distributions with ties.
    """
    if not (0.5 < confidence_level < 1.0):
        raise ValueError(f"confidence_level must be between 0.5 and 1.0, got {confidence_level}")

    n = len(scores)
    theta_hat = sum(scores) / n
    rng = random.Random(seed)

    # 1. Bootstrap replicates
    boot_means: list[float] = []
    for _ in range(replicates):
        sample = [scores[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()

    norm = statistics.NormalDist()

    # 2. Bias-correction parameter z0 (tie-aware: N_< + 0.5 * N_=)
    n_less = sum(1 for m in boot_means if m < theta_hat)
    n_equal = sum(1 for m in boot_means if abs(m - theta_hat) < 1e-12)
    prop = (n_less + 0.5 * n_equal) / replicates
    prop = max(1e-6, min(1.0 - 1e-6, prop))
    z0 = norm.inv_cdf(prop)

    # 3. Acceleration parameter a from jackknife
    total_score = sum(scores)
    jack_means = [(total_score - scores[i]) / (n - 1) for i in range(n)]
    jack_mean_bar = sum(jack_means) / n

    diffs = [jack_mean_bar - jm for jm in jack_means]
    sum_cubed = sum(d**3 for d in diffs)
    sum_squared = sum(d**2 for d in diffs)

    a = 0.0 if sum_squared < 1e-12 else sum_cubed / (6.0 * (sum_squared**1.5))

    # 4. Adjusted percentiles
    alpha = 1.0 - confidence_level
    z_alpha_half = norm.inv_cdf(alpha / 2.0)
    z_1_minus_alpha_half = norm.inv_cdf(1.0 - alpha / 2.0)

    def _calc_pct(z_val: float) -> float:
        denom = 1.0 - a * (z0 + z_val)
        if abs(denom) < 1e-6:
            denom = 1e-6 if denom >= 0 else -1e-6
        adj_z = z0 + (z0 + z_val) / denom
        return norm.cdf(adj_z)

    pct_low = _calc_pct(z_alpha_half)
    pct_high = _calc_pct(z_1_minus_alpha_half)

    pct_low = max(0.0001, min(0.9999, pct_low))
    pct_high = max(0.0001, min(0.9999, pct_high))
    if pct_low > pct_high:
        pct_low, pct_high = pct_high, pct_low

    idx_low = int(pct_low * (replicates - 1))
    idx_high = int(pct_high * (replicates - 1))

    return boot_means[idx_low], boot_means[idx_high]


def compute_continuous_score_ci(
    scores: list[float],
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute confidence interval for continuous scores in [0.0, 1.0].

    Honors requested confidence_level in (0.5, 1.0).
    Uses degenerate interval when all scores are identical or N < 2.
    Uses Student's t-distribution for small non-degenerate samples (2 <= N <= 20).
    Uses Bias-Corrected and Accelerated (BCa) bootstrap for larger samples (N > 20).
    """
    if not (0.5 < confidence_level < 1.0):
        raise ValueError(f"confidence_level must be between 0.5 and 1.0, got {confidence_level}")

    n = len(scores)
    if n <= 0:
        return ConfidenceInterval(
            lower=0.0, upper=0.0, confidence_level=confidence_level, method="degenerate"
        )
    if n == 1 or (max(scores) - min(scores)) < 1e-9:
        val = max(0.0, min(1.0, scores[0]))
        return ConfidenceInterval(
            lower=round(val, 4),
            upper=round(val, 4),
            confidence_level=confidence_level,
            method="degenerate",
        )

    mean = sum(scores) / n
    variance = sum((x - mean) ** 2 for x in scores) / (n - 1)
    std_dev = math.sqrt(variance)
    se = std_dev / math.sqrt(n)

    if n <= 20:
        df = n - 1
        t_crit = _get_student_t_critical(df, confidence_level=confidence_level)
        lower = max(0.0, mean - t_crit * se)
        upper = min(1.0, mean + t_crit * se)
        return ConfidenceInterval(
            lower=round(lower, 4),
            upper=round(upper, 4),
            confidence_level=confidence_level,
            method="student_t",
        )

    # For N > 20: True Bias-Corrected and Accelerated (BCa) Bootstrap
    bca_low, bca_high = _compute_bca_interval(scores, confidence_level=confidence_level)
    lower = max(0.0, min(1.0, bca_low))
    upper = max(0.0, min(1.0, bca_high))
    return ConfidenceInterval(
        lower=round(lower, 4),
        upper=round(upper, 4),
        confidence_level=confidence_level,
        method="bootstrap_bca",
    )


def compute_decision_consistency(episodes: list[EpisodeResult]) -> float:
    """Compute modal frequency of (task_success, trap_triggered, terminal_action) across seeds."""
    if not episodes:
        return 1.0
    signatures = [
        (ep.task_success, ep.trap_triggered, ep.terminal_action or "none") for ep in episodes
    ]
    counts = Counter(signatures)
    most_common_count = counts.most_common(1)[0][1]
    return round(most_common_count / len(episodes), 4)


def compute_trajectory_jaccard_consistency(episodes: list[EpisodeResult]) -> float:
    """Compute mean pairwise Jaccard similarity of distinct action sets across seed pairs."""
    n = len(episodes)
    if n <= 1:
        return 1.0

    action_sets = [set(ep.action_sequence) for ep in episodes]
    pair_count = 0
    jaccard_sum = 0.0

    for i in range(n):
        for j in range(i + 1, n):
            s1 = action_sets[i]
            s2 = action_sets[j]
            union_len = len(s1 | s2)
            sim = 1.0 if union_len == 0 else len(s1 & s2) / union_len
            jaccard_sum += sim
            pair_count += 1

    return round(jaccard_sum / pair_count, 4) if pair_count > 0 else 1.0


def aggregate_group(
    provider: str,
    model_id: str,
    environment_name: str,
    variant: str,
    episodes: list[EpisodeResult],
) -> MultiSeedAggregateResult:
    """Aggregate a collection of completed episode results for one (model, env, variant) group."""
    completed = [ep for ep in episodes if ep.status == EpisodeStatus.COMPLETED]
    n = len(completed)
    failed_count = len(episodes) - n

    # Failure breakdown
    failure_counts = Counter(ep.primary_failure_reason for ep in episodes)
    failure_breakdown = PrimaryFailureBreakdown(
        none_count=failure_counts.get(PrimaryFailureReason.NONE, 0),
        provider_error_count=failure_counts.get(PrimaryFailureReason.PROVIDER_ERROR, 0),
        context_overflow_count=failure_counts.get(PrimaryFailureReason.CONTEXT_OVERFLOW, 0),
        parse_failure_count=failure_counts.get(PrimaryFailureReason.PARSE_FAILURE, 0),
        invalid_action_count=failure_counts.get(PrimaryFailureReason.INVALID_ACTION, 0),
        task_failure_count=failure_counts.get(PrimaryFailureReason.TASK_FAILURE, 0),
    )

    # Operational reliability
    total_episodes_count = len(episodes)
    op_success_count = sum(
        1
        for ep in episodes
        if ep.primary_failure_reason
        not in (
            PrimaryFailureReason.PROVIDER_ERROR,
            PrimaryFailureReason.CONTEXT_OVERFLOW,
            PrimaryFailureReason.PARSE_FAILURE,
        )
    )
    op_success_rate = (
        round(op_success_count / total_episodes_count, 4) if total_episodes_count > 0 else 0.0
    )
    op_success_ci = compute_wilson_score_interval(op_success_count, total_episodes_count)

    clean_parse_count = sum(1 for ep in episodes if ep.parse_failure_count == 0)
    parse_reliability = (
        round(clean_parse_count / total_episodes_count, 4) if total_episodes_count > 0 else 0.0
    )
    parse_rel_ci = compute_wilson_score_interval(clean_parse_count, total_episodes_count)

    e2e_successes = sum(1 for ep in episodes if ep.task_success)
    e2e_rate = round(e2e_successes / total_episodes_count, 4) if total_episodes_count > 0 else 0.0
    e2e_ci = compute_wilson_score_interval(e2e_successes, total_episodes_count)

    if op_success_count > 0:
        parsed_task_successes = sum(
            1
            for ep in episodes
            if ep.task_success
            and ep.primary_failure_reason
            not in (
                PrimaryFailureReason.PROVIDER_ERROR,
                PrimaryFailureReason.CONTEXT_OVERFLOW,
                PrimaryFailureReason.PARSE_FAILURE,
            )
        )
        parsed_task_rate: float | None = round(parsed_task_successes / op_success_count, 4)
        parsed_task_ci: ConfidenceInterval | None = compute_wilson_score_interval(
            parsed_task_successes, op_success_count
        )
    else:
        parsed_task_rate = None
        parsed_task_ci = None

    operational_reliability = OperationalReliabilitySummary(
        total_episodes=total_episodes_count,
        operational_success_count=op_success_count,
        operational_success_rate=op_success_rate,
        operational_success_wilson_ci=op_success_ci,
        parse_failure_episodes=sum(1 for ep in episodes if ep.parse_failure_count > 0),
        parse_reliability_rate=parse_reliability,
        parse_reliability_wilson_ci=parse_rel_ci,
        invalid_action_episodes=sum(1 for ep in episodes if ep.invalid_action_count > 0),
        context_overflow_episodes=sum(1 for ep in episodes if ep.context_overflow_count > 0),
        provider_error_episodes=sum(
            1
            for ep in episodes
            if ep.provider_error_count > 0 or ep.status != EpisodeStatus.COMPLETED
        ),
        end_to_end_success_rate=e2e_rate,
        end_to_end_success_wilson_ci=e2e_ci,
        parsed_task_success_rate=parsed_task_rate,
        parsed_task_success_wilson_ci=parsed_task_ci,
    )

    # Trap summary (explicit denominators; None for control variant)
    trap_summary: TrapRateSummary | None = (
        None if variant == "control" else compute_trap_rates(episodes)
    )

    if n == 0:
        # Fallback for groups where all episodes failed technical infrastructure
        return MultiSeedAggregateResult(
            provider=provider,
            model_id=model_id,
            environment_name=environment_name,
            variant=variant,  # type: ignore[arg-type]
            sample_size_n=len(episodes) or 1,
            seeds_evaluated=[ep.spec.seed for ep in episodes],
            failed_episodes_count=failed_count,
            mean_score=0.0,
            median_score=0.0,
            variance_score=0.0,
            std_dev_score=0.0,
            std_error_score=0.0,
            score_ci_95=ConfidenceInterval(lower=0.0, upper=0.0, method="degenerate"),
            min_score=0.0,
            max_score=0.0,
            task_success_rate=0.0,
            task_success_wilson_ci=ConfidenceInterval(lower=0.0, upper=0.0, method="degenerate"),
            trap_fall_rate=None if variant == "control" else 0.0,
            trap_fall_wilson_ci=None
            if variant == "control"
            else ConfidenceInterval(lower=0.0, upper=0.0, method="degenerate"),
            trap_summary=trap_summary,
            operational_reliability=operational_reliability,
            failure_breakdown=failure_breakdown,
        )

    scores = [ep.raw_score for ep in completed]
    sorted_scores = sorted(scores)
    seeds = [ep.spec.seed for ep in completed]

    mean_s = sum(scores) / n
    median_s = (
        sorted_scores[n // 2]
        if n % 2 != 0
        else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0
    )
    var_s = sum((x - mean_s) ** 2 for x in scores) / (n - 1) if n > 1 else 0.0
    std_s = math.sqrt(var_s)
    se_s = std_s / math.sqrt(n)

    score_ci = compute_continuous_score_ci(scores)

    # Success rate
    successes = sum(1 for ep in completed if ep.task_success)
    success_rate = successes / n
    success_ci = compute_wilson_score_interval(successes, n)

    # Trap fall rate: None for control variant per LLM 2 recommendation
    if variant == "control":
        trap_rate = None
        trap_ci = None
    else:
        traps = sum(1 for ep in completed if ep.trap_triggered)
        trap_rate = round(traps / n, 4)
        trap_ci = compute_wilson_score_interval(traps, n)

    # Evidence violation rate
    evidence_violations = sum(1 for ep in completed if ep.evidence_before_mutation_violated)
    evidence_rate = round(evidence_violations / n, 4)

    # Parse failure rate
    parse_failures = sum(1 for ep in completed if ep.parse_failure_count > 0)
    parse_rate = round(parse_failures / n, 4)

    # Consistency metrics
    decision_cons = compute_decision_consistency(completed)
    traj_cons = compute_trajectory_jaccard_consistency(completed)

    # Pass@k interpretations
    pass_at_1 = round(success_rate, 4)
    pass_all_k = 1.0 if (successes == n and (trap_rate is None or trap_rate == 0.0)) else 0.0

    mean_steps = round(sum(ep.steps_taken for ep in completed) / n, 2)
    mean_lat = round(sum(ep.total_latency_ms for ep in completed) / n, 2)

    return MultiSeedAggregateResult(
        provider=provider,
        model_id=model_id,
        environment_name=environment_name,
        variant=variant,  # type: ignore[arg-type]
        sample_size_n=n,
        seeds_evaluated=seeds,
        failed_episodes_count=failed_count,
        mean_score=round(mean_s, 4),
        median_score=round(median_s, 4),
        variance_score=round(var_s, 4),
        std_dev_score=round(std_s, 4),
        std_error_score=round(se_s, 4),
        score_ci_95=score_ci,
        min_score=round(min(scores), 4),
        max_score=round(max(scores), 4),
        task_success_rate=round(success_rate, 4),
        task_success_wilson_ci=success_ci,
        trap_fall_rate=trap_rate,
        trap_fall_wilson_ci=trap_ci,
        evidence_violation_rate=evidence_rate,
        parse_failure_episode_rate=parse_rate,
        terminal_decision_consistency=decision_cons,
        trajectory_jaccard_consistency=traj_cons,
        pass_at_1=pass_at_1,
        pass_all_k=pass_all_k,
        mean_steps=mean_steps,
        mean_latency_ms=mean_lat,
        trap_summary=trap_summary,
        operational_reliability=operational_reliability,
        failure_breakdown=failure_breakdown,
    )


def aggregate_suite_results(episodes: list[EpisodeResult]) -> list[MultiSeedAggregateResult]:
    """Partition all completed episode results by (provider, model, env, variant) and aggregate."""
    groups: dict[tuple[str, str, str, str], list[EpisodeResult]] = {}
    for ep in episodes:
        key = (ep.spec.provider, ep.spec.model_id, ep.spec.environment_name, ep.spec.variant)
        groups.setdefault(key, []).append(ep)

    aggregates: list[MultiSeedAggregateResult] = []
    for (provider, model_id, env_name, variant), ep_list in sorted(groups.items()):
        aggregates.append(
            aggregate_group(
                provider=provider,
                model_id=model_id,
                environment_name=env_name,
                variant=variant,
                episodes=ep_list,
            )
        )
    return aggregates


def compute_adversarial_deltas(
    aggregates: list[MultiSeedAggregateResult],
) -> dict[str, dict[str, float]]:
    """Compute paired control-minus-standard score deltas per model and environment."""
    std_scores: dict[tuple[str, str], float] = {}
    ctl_scores: dict[tuple[str, str], float] = {}

    for agg in aggregates:
        k = (agg.model_id, agg.environment_name)
        if agg.variant == "standard":
            std_scores[k] = agg.mean_score
        elif agg.variant == "control":
            ctl_scores[k] = agg.mean_score

    deltas: dict[str, dict[str, float]] = {}
    for (model_id, env_name), ctl_s in ctl_scores.items():
        if (model_id, env_name) in std_scores:
            std_s = std_scores[(model_id, env_name)]
            diff = round(ctl_s - std_s, 4)
            deltas.setdefault(model_id, {})[env_name] = diff

    return deltas
