"""Unified CLI parser and execution runner for multi-seed benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS
from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager
from agent_praxis.framework.runner.multiseed.executor import MultiSeedExecutor
from agent_praxis.framework.runner.multiseed.matrix import expand_workload_matrix
from agent_praxis.framework.runner.multiseed.schemas import (
    BenchmarkRunManifest,
    BenchmarkSuiteReport,
    DecodingParameters,
    ExecutionTier,
    SeedStrategy,
)
from agent_praxis.framework.runner.multiseed.seeds import get_tier_seed_config


def add_multiseed_cli_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach standardized multi-seed arguments to any runner script."""
    group = parser.add_argument_group("Multi-Seed Execution & Statistical Engine")

    group.add_argument(
        "--tier",
        type=str,
        choices=[t.value for t in ExecutionTier],
        default=ExecutionTier.FULL.value,
        help="Execution tier preset controlling default seed counts and variants.",
    )
    group.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Comma-separated explicit seeds (e.g. '20260201,20260202'). Overrides --num-seeds.",
    )
    group.add_argument(
        "--num-seeds",
        type=int,
        default=None,
        help="Number of seeds per (environment, variant) pair. Overrides tier default.",
    )
    group.add_argument(
        "--seed-strategy",
        type=str,
        choices=[s.value for s in SeedStrategy],
        default=None,
        help="Seed generation strategy: canonical | explicit | sequential | prng.",
    )
    group.add_argument(
        "--variants",
        type=str,
        default=None,
        help="Comma-separated variants to evaluate (e.g. 'standard,control' or 'standard').",
    )
    group.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Maximum total concurrent evaluation episodes across all workers.",
    )
    group.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Max exponential-backoff retries per turn on transient API/network failures.",
    )
    group.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Path to an existing .wal.jsonl to resume interrupted runs.",
    )
    group.add_argument(
        "--output",
        type=str,
        default="results/benchmark_report.json",
        help="Output path for the compiled BenchmarkSuiteReport JSON.",
    )
    return parser


def format_summary_table(report: BenchmarkSuiteReport) -> str:
    """Format MultiSeedAggregateResults into a readable markdown table."""
    lines = [
        "| Environment | Variant | N | Mean Score (95% CI) | Success Rate | Trap-Fall Rate | Consistency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for agg in report.aggregates:
        ci_str = f"[{agg.score_ci_95.lower:.2f}, {agg.score_ci_95.upper:.2f}]"
        succ_str = f"{int(agg.task_success_rate * 100)}%"
        trap_str = f"{int(agg.trap_fall_rate * 100)}%" if agg.trap_fall_rate is not None else "N/A"
        cons_str = f"{int(agg.terminal_decision_consistency * 100)}%"
        lines.append(
            f"| {agg.environment_name} | {agg.variant} | {agg.sample_size_n} | "
            f"{agg.mean_score:.3f} {ci_str} | {succ_str} | {trap_str} | {cons_str} |"
        )
    return "\n".join(lines)


async def async_main(args: argparse.Namespace) -> int:
    tier = ExecutionTier(args.tier)
    strat = SeedStrategy(args.seed_strategy) if args.seed_strategy else None

    explicit_seeds_list = None
    if args.seeds:
        explicit_seeds_list = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    seed_cfg = get_tier_seed_config(
        tier=tier,
        explicit_seeds=explicit_seeds_list,
        num_seeds=args.num_seeds,
        strategy=strat,
    )

    if args.variants:
        variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    elif tier == ExecutionTier.CI:
        variants = ["standard"]
    else:
        variants = ["standard", "control"]

    models_raw = getattr(args, "models", ["mock-policy"])
    models: list[tuple[str, str]] = []
    for m in models_raw:
        provider = "mock"
        if "llama" in m.lower():
            provider = "ollama"
        elif "groq" in m.lower():
            provider = "groq"
        elif "meta" in m.lower():
            provider = "meta"
        models.append((m, provider))

    envs = getattr(args, "envs", list(ENV_SPECS.keys()))

    output_path = Path(args.output)
    wal_path = Path(args.resume_from) if args.resume_from else output_path.with_suffix(".wal.jsonl")

    checkpoint_mgr = CheckpointManager(wal_path)
    specs = expand_workload_matrix(
        models=models,
        environments=envs,
        variants=variants,  # type: ignore[arg-type]
        seed_config=seed_cfg,
        decoding=DecodingParameters(),
    )

    print(
        f"\nStarting Agent Praxis Multi-Seed Runner:\n"
        f"  Tier: {tier.value}\n"
        f"  Workload: {len(specs)} episodes ({len(models)} models × {len(envs)} envs × {len(variants)} variants × {seed_cfg.num_seeds} seeds)\n"
        f"  Concurrency: {args.concurrency}\n"
        f"  WAL path: {wal_path}\n"
        f"  Output path: {output_path}\n"
    )

    executor = MultiSeedExecutor(
        checkpoint_manager=checkpoint_mgr,
        concurrency=args.concurrency,
        max_retries=args.max_retries,
    )

    manifest = BenchmarkRunManifest(
        run_id=f"run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        execution_tier=tier,
        seed_config=seed_cfg,
        started_at_utc=datetime.now(UTC),
    )

    await executor.run_suite(specs)
    manifest.completed_at_utc = datetime.now(UTC)

    report = checkpoint_mgr.compile_final_report(manifest, output_path)

    print("\n" + "=" * 70)
    print("AGENT PRAXIS MULTI-SEED BENCHMARK REPORT")
    print("=" * 70)
    print(format_summary_table(report))
    print(f"\nFinal report saved to {output_path}.\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Praxis Multi-Seed Evaluation Engine")
    parser.add_argument(
        "--models", nargs="+", default=["mock-policy"], help="Model identifiers to evaluate."
    )
    parser.add_argument(
        "--envs", nargs="+", default=list(ENV_SPECS.keys()), help="Target environments."
    )
    add_multiseed_cli_args(parser)
    args = parser.parse_args()

    sys.exit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
