"""Defensible Benchmark Result Aggregator with Bootstrap 95% Confidence Intervals.

Reads an Agent Praxis benchmark result JSON document (with full provenance and raw responses),
computes exact sample statistics, bootstrap 95% confidence intervals, trap-fall rates, and
parse-fail rates per environment and overall aggregate.

Usage::
    python tools/aggregate_benchmark_results.py results/sarvam-105b_standard_10seed.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def bootstrap_ci_mean(
    values: list[float], n_resamples: int = 10000, ci: float = 0.95, seed: int = 42
) -> tuple[float, float]:
    """Compute non-parametric percentile bootstrap confidence interval for the mean."""
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]
    if all(v == values[0] for v in values):
        return values[0], values[0]

    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = rng.choices(values, k=n)
        means.append(sum(sample) / n)

    means.sort()
    lower_idx = int((1.0 - ci) / 2.0 * n_resamples)
    upper_idx = int((1.0 + ci) / 2.0 * n_resamples) - 1
    lower_idx = max(0, min(lower_idx, n_resamples - 1))
    upper_idx = max(0, min(upper_idx, n_resamples - 1))
    return means[lower_idx], means[upper_idx]


def compute_median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def compute_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(runs)
    if n == 0:
        return {}

    scores = [float(r.get("score", 0.0)) for r in runs]
    mean = sum(scores) / n
    variance = sum((x - mean) ** 2 for x in scores) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(variance)
    median = compute_median(scores)
    ci_low, ci_high = bootstrap_ci_mean(scores)

    success_count = sum(1 for r in runs if bool(r.get("task_success", False)))
    compliance_count = sum(1 for r in runs if bool(r.get("constraint_compliance", False)))
    # Trap fall is specifically violating constraints (passive inaction is compliance=True, success=False)
    trap_fall_count = n - compliance_count
    runs_with_parse_fail = sum(1 for r in runs if int(r.get("parse_failures", 0) or 0) > 0)
    total_parse_fails = sum(int(r.get("parse_failures", 0) or 0) for r in runs)
    avg_steps = sum(int(r.get("steps", 0) or 0) for r in runs) / n

    return {
        "n_runs": n,
        "mean": round(mean, 4),
        "median": round(median, 4),
        "std": round(std, 4),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "ci_95": (round(ci_low, 4), round(ci_high, 4)),
        "success_rate": round(success_count / n, 4),
        "compliance_rate": round(compliance_count / n, 4),
        "trap_fall_rate": round(trap_fall_count / n, 4),
        "parse_fail_rate": round(runs_with_parse_fail / n, 4),
        "total_parse_failures": total_parse_fails,
        "avg_steps": round(avg_steps, 2),
    }


def aggregate_artifact(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Flatten runs by model and environment
    all_runs: list[dict[str, Any]] = []
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                runs = entry.get("runs")
                if isinstance(runs, list):
                    all_runs.extend(runs)
                elif "score" in entry:
                    all_runs.append(entry)
    elif isinstance(data, dict):
        all_runs = data.get("runs", [])

    if not all_runs:
        raise ValueError(f"No valid run records found in {path}")

    # Group by (model, environment)
    by_model_env: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_model: dict[str, list[dict[str, Any]]] = {}

    for r in all_runs:
        m = r.get("model", "unknown")
        e = r.get("environment", "unknown")
        by_model_env.setdefault((m, e), []).append(r)
        by_model.setdefault(m, []).append(r)

    models = sorted(by_model.keys())
    results: dict[str, Any] = {}

    for model in models:
        m_runs = by_model[model]
        env_names = sorted({r.get("environment", "unknown") for r in m_runs})
        env_breakdown: dict[str, Any] = {}
        for env in env_names:
            runs = by_model_env.get((model, env), [])
            env_breakdown[env] = compute_metrics(runs)

        results[model] = {
            "environments": env_breakdown,
            "overall": compute_metrics(m_runs),
        }

    return results


def format_markdown_table(agg: dict[str, Any]) -> str:
    lines = [
        "| Model | Environment | N | Mean Score | 95% Bootstrap CI | Median | Min – Max | Std Dev | Success | Compliance | Trap Fall | Parse Fail |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for model, m_data in agg.items():
        envs = m_data.get("environments", {})
        for env_name, st in envs.items():
            ci = st["ci_95"]
            ci_str = f"[{ci[0]:.3f}, {ci[1]:.3f}]"
            lines.append(
                f"| **{model}** | {env_name} | {st['n_runs']} | "
                f"**{st['mean']:.3f}** | {ci_str} | {st['median']:.3f} | "
                f"{st['min']:.3f} – {st['max']:.3f} | ±{st['std']:.3f} | "
                f"{int(st['success_rate'] * 100)}% | {int(st['compliance_rate'] * 100)}% | "
                f"{int(st['trap_fall_rate'] * 100)}% | {int(st['parse_fail_rate'] * 100)}% |"
            )

        ov = m_data.get("overall", {})
        if ov:
            ci = ov["ci_95"]
            ci_str = f"[{ci[0]:.3f}, {ci[1]:.3f}]"
            lines.append(
                f"| **{model}** | **OVERALL AGGREGATE** | **{ov['n_runs']}** | "
                f"**{ov['mean']:.3f}** | **{ci_str}** | **{ov['median']:.3f}** | "
                f"**{ov['min']:.3f} – {ov['max']:.3f}** | **±{ov['std']:.3f}** | "
                f"**{int(ov['success_rate'] * 100)}%** | **{int(ov['compliance_rate'] * 100)}%** | "
                f"**{int(ov['trap_fall_rate'] * 100)}%** | **{int(ov['parse_fail_rate'] * 100)}%** |"
            )
        lines.append("| | | | | | | | | | | | |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate Agent Praxis Benchmark Results")
    parser.add_argument("artifacts", nargs="+", help="Path(s) to benchmark results JSON files")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON instead of markdown")
    args = parser.parse_args()

    for artifact_str in args.artifacts:
        path = Path(artifact_str)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            continue

        agg = aggregate_artifact(path)
        if args.json:
            print(json.dumps(agg, indent=2))
        else:
            print(f"\nAGGREGATED BENCHMARK REPORT: {path.name}")
            print("=" * 70)
            print(format_markdown_table(agg))


if __name__ == "__main__":
    main()
