"""Statistical aggregation engine for multi-seed benchmark evaluations.

Implements small-sample Wilson score intervals, Student-t confidence intervals,
bootstrap resamplers, and behavioral consistency metrics.
"""

from __future__ import annotations

import math
import random
from collections import Counter

from agent_praxis.framework.runner.multiseed.schemas import (
    ConfidenceInterval,
    EpisodeResult,
    EpisodeStatus,
    MultiSeedAggregateResult,
)

# Two-tailed t critical values at alpha=0.05 (95% confidence) for degrees of freedom 1..20
_STUDENT_T_CRITICAL_95: dict[int, float] = {
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
}


def compute_wilson_score_interval(
    successes: int,
    total: int,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute the Wilson score interval for a binomial proportion.

    Accurate even for small N or extreme proportions (e.g. 0% or 100% success).
    """
    if total <= 0:
        return ConfidenceInterval(lower=0.0, upper=0.0, method="degenerate")

    z = 1.959963984540054  # 95% two-sided normal quantile
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


def compute_continuous_score_ci(
    scores: list[float],
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute 95% confidence interval for continuous scores in [0.0, 1.0].

    Uses Student's t-distribution for N <= 20, or percentile bootstrap for larger samples.
    """
    n = len(scores)
    if n <= 0:
        return ConfidenceInterval(lower=0.0, upper=0.0, method="degenerate")
    if n == 1:
        val = max(0.0, min(1.0, scores[0]))
        return ConfidenceInterval(lower=val, upper=val, method="degenerate")

    mean = sum(scores) / n
    variance = sum((x - mean) ** 2 for x in scores) / (n - 1)
    std_dev = math.sqrt(variance)
    se = std_dev / math.sqrt(n)

    if n <= 20:
        df = n - 1
        t_crit = _STUDENT_T_CRITICAL_95.get(df, 2.086)
        lower = max(0.0, mean - t_crit * se)
        upper = min(1.0, mean + t_crit * se)
        return ConfidenceInterval(
            lower=round(lower, 4),
            upper=round(upper, 4),
            confidence_level=confidence_level,
            method="student_t",
        )

    # For N > 20: Deterministic Percentile Bootstrap (B = 1000)
    rng = random.Random(42)
    means: list[float] = []
    for _ in range(1000):
        sample = [scores[rng.randint(0, n - 1)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lower = max(0.0, means[int(0.025 * 1000)])
    upper = min(1.0, means[int(0.975 * 1000)])
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
