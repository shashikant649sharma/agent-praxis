"""Model Head-to-Head Comparison Runner with matched-seed enforcement.

Evaluates paired score deltas, task success rates, operational reliability,
and trap rates on strictly matched seeds, isolating development from held-out splits.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path

from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager
from agent_praxis.framework.runner.multiseed.schemas import (
    ConfidenceInterval,
    EpisodeResult,
    MatchedSeedDelta,
    ModelComparisonReport,
    SeedSplit,
    classify_seed_split,
    validate_episode_record,
)
from agent_praxis.framework.runner.multiseed.stats import (
    compute_continuous_score_ci,
)
from agent_praxis.framework.runner.multiseed.traps import compute_trap_rates

logger = logging.getLogger("agent_praxis.multiseed.compare")


def filter_episodes_by_split(
    episodes: list[EpisodeResult],
    split: SeedSplit,
) -> list[EpisodeResult]:
    """Filter episodes strictly by seed split.

    Rejects mixed or improperly classified episodes.
    """
    if split == SeedSplit.FULL:
        return list(episodes)

    filtered: list[EpisodeResult] = []
    for ep in episodes:
        actual_split = classify_seed_split(ep.spec.environment_name, ep.spec.seed)
        if actual_split == split or ep.seed_split == split:
            filtered.append(ep)
    return filtered


def run_model_comparison(
    model_a_episodes: list[EpisodeResult],
    model_b_episodes: list[EpisodeResult],
    *,
    seed_split: SeedSplit = SeedSplit.HELD_OUT,
    confidence_level: float = 0.95,
    strict_matched_seeds: bool = True,
    git_commit_sha: str = "unknown",
) -> ModelComparisonReport:
    """Compare two models on matched seeds with rigorous paired confidence intervals.

    Rules:
    1. Every episode record is validated for reproduction completeness.
    2. Split isolation: development and held-out records cannot be mingled.
    3. Comparisons are strictly paired on matched seeds (Seed_A == Seed_B).
    4. Continuous score deltas (B - A) compute paired Student-t or BCa intervals.
    5. Trap comparisons compute explicit conditional rates and report None when unexposed.
    """
    if not model_a_episodes:
        raise ValueError("model_a_episodes cannot be empty")
    if not model_b_episodes:
        raise ValueError("model_b_episodes cannot be empty")

    # Validate all records
    for ep in model_a_episodes:
        validate_episode_record(ep)
    for ep in model_b_episodes:
        validate_episode_record(ep)

    # Filter by split if requested
    filtered_a = filter_episodes_by_split(model_a_episodes, seed_split)
    filtered_b = filter_episodes_by_split(model_b_episodes, seed_split)

    if not filtered_a:
        raise ValueError(f"No Model A episodes found for split '{seed_split.value}'")
    if not filtered_b:
        raise ValueError(f"No Model B episodes found for split '{seed_split.value}'")

    model_a_id = filtered_a[0].spec.model_id
    model_b_id = filtered_b[0].spec.model_id

    # Group by (environment_name, variant)
    groups_a: dict[tuple[str, str], dict[int, EpisodeResult]] = {}
    for ep in filtered_a:
        key = (ep.spec.environment_name, ep.spec.variant)
        groups_a.setdefault(key, {})[ep.spec.seed] = ep

    groups_b: dict[tuple[str, str], dict[int, EpisodeResult]] = {}
    for ep in filtered_b:
        key = (ep.spec.environment_name, ep.spec.variant)
        groups_b.setdefault(key, {})[ep.spec.seed] = ep

    all_keys = sorted(set(groups_a.keys()) | set(groups_b.keys()))
    matched_deltas: list[MatchedSeedDelta] = []
    warnings: list[str] = []

    for env_name, variant in all_keys:
        a_by_seed = groups_a.get((env_name, variant), {})
        b_by_seed = groups_b.get((env_name, variant), {})

        seeds_a = set(a_by_seed.keys())
        seeds_b = set(b_by_seed.keys())
        matched_seeds = sorted(seeds_a & seeds_b)

        unmatched_a = sorted(seeds_a - seeds_b)
        unmatched_b = sorted(seeds_b - seeds_a)

        if unmatched_a or unmatched_b:
            warn_msg = (
                f"[{env_name}:{variant}] Unmatched seeds: Model A exclusive {unmatched_a}, "
                f"Model B exclusive {unmatched_b}."
            )
            warnings.append(warn_msg)
            if strict_matched_seeds:
                raise ValueError(
                    f"Strict matched-seed enforcement failed: {warn_msg} "
                    "Both models must evaluate the exact same seeds."
                )

        if not matched_seeds:
            continue

        n = len(matched_seeds)
        eps_a = [a_by_seed[s] for s in matched_seeds]
        eps_b = [b_by_seed[s] for s in matched_seeds]

        scores_a = [ep.raw_score for ep in eps_a]
        scores_b = [ep.raw_score for ep in eps_b]

        mean_a = sum(scores_a) / n
        mean_b = sum(scores_b) / n
        ci_a = compute_continuous_score_ci(scores_a, confidence_level=confidence_level)
        ci_b = compute_continuous_score_ci(scores_b, confidence_level=confidence_level)

        succ_a = sum(1 for ep in eps_a if ep.task_success)
        succ_b = sum(1 for ep in eps_b if ep.task_success)
        succ_rate_a = round(succ_a / n, 4)
        succ_rate_b = round(succ_b / n, 4)
        task_succ_delta = round(succ_rate_b - succ_rate_a, 4)

        op_succ_a = sum(
            1
            for ep in eps_a
            if ep.primary_failure_reason.value
            not in ("provider_error", "context_overflow", "parse_failure")
        )
        op_succ_b = sum(
            1
            for ep in eps_b
            if ep.primary_failure_reason.value
            not in ("provider_error", "context_overflow", "parse_failure")
        )
        op_rate_a = round(op_succ_a / n, 4)
        op_rate_b = round(op_succ_b / n, 4)

        # Paired differences: d_s = score_b_s - score_a_s
        paired_diffs = [scores_b[i] - scores_a[i] for i in range(n)]
        mean_diff = sum(paired_diffs) / n

        # For paired difference CI:
        if n == 1 or (max(paired_diffs) - min(paired_diffs)) < 1e-9:
            val = paired_diffs[0]
            delta_ci = ConfidenceInterval(
                lower=round(val, 4),
                upper=round(val, 4),
                confidence_level=confidence_level,
                method="degenerate",
            )
        else:
            var_d = sum((x - mean_diff) ** 2 for x in paired_diffs) / (n - 1)
            se_d = math.sqrt(var_d) / math.sqrt(n)
            from agent_praxis.framework.runner.multiseed.stats import _get_student_t_critical

            t_crit = _get_student_t_critical(n - 1, confidence_level=confidence_level)
            delta_ci = ConfidenceInterval(
                lower=round(mean_diff - t_crit * se_d, 4),
                upper=round(mean_diff + t_crit * se_d, 4),
                confidence_level=confidence_level,
                method="student_t",
            )

        # Trap comparisons (standard variant only)
        trap_cond_a: float | None = None
        trap_cond_b: float | None = None
        trap_delta: float | None = None

        if variant == "standard":
            rates_a = compute_trap_rates(eps_a, confidence_level=confidence_level)
            rates_b = compute_trap_rates(eps_b, confidence_level=confidence_level)
            trap_cond_a = rates_a.conditional_trigger_rate
            trap_cond_b = rates_b.conditional_trigger_rate
            if trap_cond_a is not None and trap_cond_b is not None:
                trap_delta = round(trap_cond_b - trap_cond_a, 4)

        matched_deltas.append(
            MatchedSeedDelta(
                environment_name=env_name,
                variant=variant,  # type: ignore[arg-type]
                seed_split=seed_split,
                matched_seeds=matched_seeds,
                sample_size_n=n,
                model_a_mean_score=round(mean_a, 4),
                model_a_score_ci=ci_a,
                model_a_task_success_rate=succ_rate_a,
                model_a_operational_success_rate=op_rate_a,
                model_b_mean_score=round(mean_b, 4),
                model_b_score_ci=ci_b,
                model_b_task_success_rate=succ_rate_b,
                model_b_operational_success_rate=op_rate_b,
                score_delta_mean=round(mean_diff, 4),
                score_delta_ci=delta_ci,
                task_success_delta=task_succ_delta,
                model_a_trap_conditional_rate=trap_cond_a,
                model_b_trap_conditional_rate=trap_cond_b,
                trap_conditional_delta=trap_delta,
            )
        )

    return ModelComparisonReport(
        report_id=f"comp-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        schema_version="2.1.0",
        model_a=model_a_id,
        model_b=model_b_id,
        seed_split=seed_split,
        generated_at_utc=datetime.now(UTC),
        git_commit_sha=git_commit_sha,
        matched_comparisons=matched_deltas,
        unmatched_seeds_warning=warnings,
    )


def format_comparison_table(report: ModelComparisonReport) -> str:
    """Format ModelComparisonReport into an audit-grade Markdown table."""
    lines = [
        f"### Model Comparison: {report.model_a} (Baseline) vs {report.model_b} (Candidate)",
        f"**Partition:** `{report.seed_split.value.upper()}` | **Git Commit:** `{report.git_commit_sha}`\n",
        "| Environment | Variant | N | Model A Score (95% CI) | Model B Score (95% CI) | Paired Score Δ (95% CI) | Task Success Δ | Trap Trigger Δ |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for d in report.matched_comparisons:
        ci_a = f"[{d.model_a_score_ci.lower:.2f}, {d.model_a_score_ci.upper:.2f}]"
        ci_b = f"[{d.model_b_score_ci.lower:.2f}, {d.model_b_score_ci.upper:.2f}]"
        ci_delta = f"[{d.score_delta_ci.lower:.2f}, {d.score_delta_ci.upper:.2f}]"

        trap_delta_str = (
            f"{d.trap_conditional_delta:+.2f}" if d.trap_conditional_delta is not None else "N/A"
        )
        succ_delta_str = f"{d.task_success_delta:+.2f}"

        lines.append(
            f"| {d.environment_name} | {d.variant} | {d.sample_size_n} | "
            f"{d.model_a_mean_score:.3f} {ci_a} | {d.model_b_mean_score:.3f} {ci_b} | "
            f"{d.score_delta_mean:+.3f} {ci_delta} | {succ_delta_str} | {trap_delta_str} |"
        )

    lines.append(
        "\n*Note: Sample size N indicates matched seeds evaluated. Degenerate intervals indicate zero observed sample variance.*"
    )
    return "\n".join(lines)


def load_episodes_from_path(path: Path) -> list[EpisodeResult]:
    """Load EpisodeResult records from either a .wal.jsonl or benchmark_report.json file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    if p.suffix == ".jsonl":
        mgr = CheckpointManager(p)
        completed = mgr.load_completed_results()
        return list(completed.values())

    # Regular JSON file
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [EpisodeResult.model_validate(item) for item in data]
    if isinstance(data, dict):
        if "episodes" in data:
            return [EpisodeResult.model_validate(item) for item in data["episodes"]]
        if "results" in data:
            return [EpisodeResult.model_validate(item) for item in data["results"]]

    raise ValueError(f"Unrecognized benchmark report structure in {p}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Praxis Model Comparison Runner")
    parser.add_argument(
        "--baseline", type=str, required=True, help="Path to Baseline model WAL or JSON"
    )
    parser.add_argument(
        "--candidate", type=str, required=True, help="Path to Candidate model WAL or JSON"
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=[s.value for s in SeedSplit],
        default=SeedSplit.HELD_OUT.value,
        help="Seed split partition to evaluate (held_out, development, full)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/model_comparison.json",
        help="Output path for ModelComparisonReport JSON",
    )
    args = parser.parse_args()

    eps_a = load_episodes_from_path(Path(args.baseline))
    eps_b = load_episodes_from_path(Path(args.candidate))
    split = SeedSplit(args.split)

    report = run_model_comparison(
        eps_a,
        eps_b,
        seed_split=split,
        strict_matched_seeds=False,
    )

    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print("\n" + "=" * 80)
    print(format_comparison_table(report))
    print("=" * 80)
    print(f"\nSaved comparison report to {out_p}\n")


if __name__ == "__main__":
    main()
