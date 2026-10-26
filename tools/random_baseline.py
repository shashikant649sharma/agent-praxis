"""Random policy baseline runner and regression gate for Agent Praxis.

Runs a uniform random policy against environments over a fixed seed set,
verifying that random agents cannot solve the adversarial tasks by chance
and stay bounded below a strict score ceiling (max_score < 0.60 per environment).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
from typing import Any

from agent_praxis.errors import CommandError
from agent_praxis.framework.evaluation.schema import make_run_result
from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS
from agent_praxis.registry import ENVIRONMENT_NAMES, get_factory

DEFAULT_SEEDS = [1000 + i for i in range(40)]
MAX_STEPS = 16


def run_random_agent(
    env_name: str,
    seed: int,
    *,
    max_steps: int = MAX_STEPS,
    policy_seed: int | None = None,
) -> dict[str, Any]:
    """Execute a uniform random policy on an environment."""
    rng = random.Random(policy_seed if policy_seed is not None else seed)
    factory = get_factory(env_name)
    env = factory(seed=seed)

    actions = [a for a in ENV_SPECS[env_name]["actions"] if a != "finalize"]
    for _ in range(max_steps):
        action_name = rng.choice(actions)
        method = getattr(env, action_name, None)
        if method is None:
            continue
        with contextlib.suppress(CommandError, TypeError, ValueError):
            method()

    with contextlib.suppress(Exception):
        env.finalize()

    snap = env.snapshot_for_evaluation()
    res = make_run_result(
        snap,
        environment_name=env_name,
        command_log=snap.get("command_log", []),
    )
    return {
        "environment": env_name,
        "seed": seed,
        "score": round(res.score, 4),
        "task_success": res.task_success,
        "constraint_compliance": res.constraint_compliance,
    }


def sweep_random_baseline(
    environments: list[str] | None = None,
    seeds: list[int] | None = None,
    max_steps: int = MAX_STEPS,
) -> dict[str, Any]:
    """Run random baseline sweep across environments and seeds."""
    if environments is None:
        environments = list(ENVIRONMENT_NAMES)
    if seeds is None:
        seeds = DEFAULT_SEEDS

    results: dict[str, Any] = {}
    for env_name in environments:
        env_runs = [run_random_agent(env_name, s, max_steps=max_steps) for s in seeds]
        scores = [r["score"] for r in env_runs]
        successes = sum(1 for r in env_runs if r["task_success"])
        results[env_name] = {
            "runs": len(env_runs),
            "mean_score": round(sum(scores) / len(scores), 4),
            "max_score": round(max(scores), 4),
            "success_count": successes,
            "success_rate": round(successes / len(env_runs), 4),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run random baseline sweep.")
    parser.add_argument("--seeds", type=int, default=40, help="Number of seeds to run")
    parser.add_argument("--steps", type=int, default=16, help="Maximum steps per episode")
    parser.add_argument(
        "--assert-ceiling", type=float, default=0.60, help="Assert max score per env < ceiling"
    )
    parser.add_argument("--write", type=str, default=None, help="Path to write JSON results")
    args = parser.parse_args()

    seeds = [1000 + i for i in range(args.seeds)]
    print(
        f"Running random policy sweep: {len(seeds)} seeds x {len(ENVIRONMENT_NAMES)} environments ({args.steps} steps)..."
    )
    summary = sweep_random_baseline(seeds=seeds, max_steps=args.steps)

    print("\n" + "=" * 70)
    print(f"{'Environment':<25} {'Mean Score':<12} {'Max Score':<12} {'Success Rate'}")
    print("-" * 70)
    overall_means = []
    overall_maxes = []
    failed_envs = []
    for env_name, data in summary.items():
        overall_means.append(data["mean_score"])
        overall_maxes.append(data["max_score"])
        print(
            f"{env_name:<25} {data['mean_score']:<12.4f} {data['max_score']:<12.4f} {data['success_count']}/{data['runs']} ({data['success_rate'] * 100:.1f}%)"
        )
        if data["max_score"] >= args.assert_ceiling:
            failed_envs.append((env_name, data["max_score"]))

    print("-" * 70)
    mean_of_means = sum(overall_means) / len(overall_means)
    print(f"{'OVERALL':<25} {mean_of_means:<12.4f} {max(overall_maxes):<12.4f}")
    print("=" * 70)

    if args.write:
        with open(args.write, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Saved random baseline artifact to {args.write}")

    if failed_envs:
        print(
            f"\nREGRESSION GATE FAILED: {len(failed_envs)} environment(s) exceeded ceiling {args.assert_ceiling}:"
        )
        for env_name, max_score in failed_envs:
            print(f"  - {env_name}: max_score={max_score}")
        raise SystemExit(1)
    print(f"\nREGRESSION GATE PASSED: All environments bounded below {args.assert_ceiling}.")


if __name__ == "__main__":
    main()
