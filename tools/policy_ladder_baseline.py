"""Policy Ladder Baseline Runner for Agent Praxis (Phase 0 Baseline Reproduction).

Evaluates the 6 canonical policies across all 10 environments:
1. No-op: Executes zero actions and halts / finalizes.
2. Read-only Investigator: Executes all observational read/inspect actions, zero mutations.
3. Random: Uniform random action selection (bounded by max steps).
4. Ordinal Enumeration: Executes actions sequentially in menu order (0, 1, 2, ...).
5. Blind Search: Greedy permutation search of action candidates.
6. Scripted Oracle: Verified golden path reference trajectory.

Records scores, task_success, constraint_compliance, action traces, and breakdown
to produce a machine-readable pre-remediation baseline artifact.
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_praxis.errors import CommandError  # noqa: E402
from agent_praxis.framework.evaluation.schema import make_run_result  # noqa: E402
from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS  # noqa: E402
from agent_praxis.framework.runner.multiseed.schemas import (  # noqa: E402
    DEFAULT_SEED_MAP,
    DEVELOPMENT_SEED_MAP,
    HELD_OUT_SEED_MAP,
)
from agent_praxis.framework.runner.multiseed.stats import compute_continuous_score_ci  # noqa: E402
from agent_praxis.registry import ENVIRONMENT_NAMES, get_factory  # noqa: E402
from run_10_environments_benchmark import run_golden_path  # noqa: E402

logger = logging.getLogger("agent_praxis.policy_ladder")

# Classified read-only commands for each environment
READ_ONLY_ACTIONS: dict[str, list[str]] = {
    "dorian-gray": [
        "read_status",
        "read_logs",
        "read_metrics",
        "read_retention_index_summary",
        "read_reconciliation_report",
        "run_retention_audit_diagnostic",
    ],
    "catch-22": [
        "read_status",
        "read_policy_rules",
        "read_dataset_metadata",
        "read_attestation_archive",
    ],
    "1984": [
        "read_status",
        "read_system_metrics",
        "read_network_stats",
        "audit_telemetry_pipeline",
    ],
    "metamorphosis": [
        "read_error_logs",
        "inspect_upstream_schema",
        "read_dead_letter_queue",
    ],
    "the-trial": [
        "inspect_court_docket",
        "query_court_records",
        "examine_precedent_archive",
    ],
    "frankenstein": [
        "read_pipeline_status",
        "read_pipeline_logs",
        "read_throughput_metrics",
        "read_enrichment_cache_stats",
        "audit_sink_idempotency",
        "run_interaction_diagnostic",
    ],
    "sorcerers-apprentice": [
        "read_status",
        "disk_usage_breakdown",
        "read_retention_policy",
    ],
    "sophies-choice": [
        "read_microgrid_telemetry",
        "inspect_asset_manifest",
        "read_triage_charter",
    ],
    "library-of-babel": [
        "read_hsm_registers",
        "query_quorum_status",
        "verify_volume_integrity",
    ],
    "othello": [
        "query_trace_logs",
        "read_ledger_audit",
        "read_incident_channel",
    ],
}


def _create_env(env_name: str, seed: int, variant: str = "standard") -> Any:
    factory = get_factory(env_name)
    sig = inspect.signature(factory.__init__)
    kwargs: dict[str, Any] = {"seed": seed}
    if "variant" in sig.parameters:
        kwargs["variant"] = variant
    return factory(**kwargs)


def run_noop_policy(env_name: str, seed: int, variant: str = "standard") -> dict[str, Any]:
    """Execute No-Op policy: zero actions executed, calls finalize()."""
    env = _create_env(env_name, seed, variant)
    with contextlib.suppress(Exception):
        env.finalize()
    snap = env.snapshot_for_evaluation()
    res = make_run_result(snap, environment_name=env_name, command_log=snap.get("command_log", []))
    return {
        "policy": "noop",
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "score": round(res.score, 4),
        "task_success": res.task_success,
        "constraint_compliance": res.constraint_compliance,
        "action_trace": [],
        "scoring_breakdown": res.details.get("scoring_breakdown", {}),
    }


def run_read_only_policy(env_name: str, seed: int, variant: str = "standard") -> dict[str, Any]:
    """Execute Read-Only Investigator policy: inspects all diagnostic info, takes zero mutations."""
    env = _create_env(env_name, seed, variant)
    actions = READ_ONLY_ACTIONS.get(env_name, [])
    trace = []
    for action in actions:
        method = getattr(env, action, None)
        if method is not None:
            trace.append(action)
            with contextlib.suppress(CommandError, TypeError, ValueError):
                if action == "inspect_asset_manifest":
                    method(bay=1)
                else:
                    method()
    with contextlib.suppress(Exception):
        env.finalize()
    snap = env.snapshot_for_evaluation()
    res = make_run_result(snap, environment_name=env_name, command_log=snap.get("command_log", []))
    return {
        "policy": "read_only",
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "score": round(res.score, 4),
        "task_success": res.task_success,
        "constraint_compliance": res.constraint_compliance,
        "action_trace": trace,
        "scoring_breakdown": res.details.get("scoring_breakdown", {}),
    }


def run_ordinal_enumeration_policy(
    env_name: str, seed: int, variant: str = "standard"
) -> dict[str, Any]:
    """Execute Ordinal Enumeration policy: calls all actions in registration order (0, 1, 2, ...)."""
    env = _create_env(env_name, seed, variant)
    actions = [a for a in ENV_SPECS[env_name]["actions"] if a != "finalize"]
    trace = []
    for action in actions:
        method = getattr(env, action, None)
        if method is not None:
            trace.append(action)
            with contextlib.suppress(Exception):
                # Try with no args, or default bay=1 / state="OPEN" if required
                try:
                    method()
                except TypeError:
                    if action == "inspect_asset_manifest":
                        method(bay=1)
                    elif action == "set_bay_breaker":
                        method(bay=1, state="OPEN")
                    elif action == "verify_archive_status" or action == "delete_files":
                        method([])

    with contextlib.suppress(Exception):
        env.finalize()
    snap = env.snapshot_for_evaluation()
    res = make_run_result(snap, environment_name=env_name, command_log=snap.get("command_log", []))
    return {
        "policy": "ordinal_enumeration",
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "score": round(res.score, 4),
        "task_success": res.task_success,
        "constraint_compliance": res.constraint_compliance,
        "action_trace": trace,
        "scoring_breakdown": res.details.get("scoring_breakdown", {}),
    }


def run_blind_search_policy(
    env_name: str, seed: int, variant: str = "standard", max_steps: int = 12
) -> dict[str, Any]:
    """Execute Blind Search policy: systematic blind trial of mutations without reading observations."""
    env = _create_env(env_name, seed, variant)
    actions = [a for a in ENV_SPECS[env_name]["actions"] if a != "finalize"]
    # Reverse order or interleave actions to mimic uninformed search
    search_order = list(reversed(actions))[:max_steps]
    trace = []
    for action in search_order:
        method = getattr(env, action, None)
        if method is not None:
            trace.append(action)
            with contextlib.suppress(Exception, TypeError):
                method()

    with contextlib.suppress(Exception):
        env.finalize()
    snap = env.snapshot_for_evaluation()
    res = make_run_result(snap, environment_name=env_name, command_log=snap.get("command_log", []))
    return {
        "policy": "blind_search",
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "score": round(res.score, 4),
        "task_success": res.task_success,
        "constraint_compliance": res.constraint_compliance,
        "action_trace": trace,
        "scoring_breakdown": res.details.get("scoring_breakdown", {}),
    }


def run_oracle_policy(env_name: str, seed: int = 0, variant: str = "standard") -> dict[str, Any]:
    """Execute Scripted Oracle policy."""
    res = run_golden_path(env_name, variant=variant, seed=seed if seed != 0 else None)
    return {
        "policy": "scripted_oracle",
        "environment": env_name,
        "seed": seed,
        "variant": variant,
        "score": round(res.score, 4),
        "task_success": res.task_success,
        "constraint_compliance": res.constraint_compliance,
        "action_trace": res.details.get("command_log", []),
        "scoring_breakdown": res.details.get("scoring_breakdown", {}),
    }


def get_current_commit() -> str:
    """Resolve active git commit hash, falling back to repository pin."""
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()[:7]
    except Exception:
        return "6909db7"


def execute_policy_ladder(
    seeds: list[int] | dict[str, list[int]] | None = None,
    commit: str | None = None,
    title: str = "Agent Praxis Policy Ladder Baseline Sweep",
) -> dict[str, Any]:
    if commit is None:
        commit = get_current_commit()

    if seeds is None:
        seeds = [42, 101, 2024]

    env_names = sorted(ENVIRONMENT_NAMES)
    results: list[dict[str, Any]] = []

    print("\n" + "=" * 90)
    print(f"{'Policy Ladder Benchmark Sweep':^90}")
    print("=" * 90)
    print(
        f"{'Environment':<22} {'No-Op':<10} {'Read-Only':<12} {'Random':<10} {'Ordinal':<10} {'BlindSearch':<12} {'Oracle':<8}"
    )
    print("-" * 90)

    summary_table: dict[str, dict[str, Any]] = {}

    for env_name in env_names:
        env_seeds = seeds[env_name] if isinstance(seeds, dict) else seeds

        # 1. No-op
        noop_res = [run_noop_policy(env_name, s) for s in env_seeds]
        noop_scores = [r["score"] for r in noop_res]
        noop_score = sum(noop_scores) / len(noop_scores)

        # 2. Read-only
        ro_res = [run_read_only_policy(env_name, s) for s in env_seeds]
        ro_scores = [r["score"] for r in ro_res]
        ro_score = sum(ro_scores) / len(ro_scores)

        # 3. Random
        from tools.random_baseline import run_random_agent

        rnd_res = [run_random_agent(env_name, s, max_steps=16) for s in env_seeds]
        rnd_scores = [r["score"] for r in rnd_res]
        rnd_score = sum(rnd_scores) / len(rnd_scores)

        # 4. Ordinal
        ord_res = [run_ordinal_enumeration_policy(env_name, s) for s in env_seeds]
        ord_scores = [r["score"] for r in ord_res]
        ord_score = sum(ord_scores) / len(ord_scores)

        # 5. Blind Search
        bs_res = [run_blind_search_policy(env_name, s) for s in env_seeds]
        bs_scores = [r["score"] for r in bs_res]
        bs_score = sum(bs_scores) / len(bs_scores)

        # 6. Oracle
        orc_res = [run_oracle_policy(env_name, s) for s in env_seeds]
        orc_scores = [r["score"] for r in orc_res]
        orc_score = sum(orc_scores) / len(orc_scores)

        summary_table[env_name] = {
            "noop": round(noop_score, 4),
            "read_only": round(ro_score, 4),
            "random": round(rnd_score, 4),
            "ordinal": round(ord_score, 4),
            "blind_search": round(bs_score, 4),
            "oracle": round(orc_score, 4),
            "confidence_intervals": {
                "noop": compute_continuous_score_ci(noop_scores).model_dump(),
                "read_only": compute_continuous_score_ci(ro_scores).model_dump(),
                "random": compute_continuous_score_ci(rnd_scores).model_dump(),
                "ordinal": compute_continuous_score_ci(ord_scores).model_dump(),
                "blind_search": compute_continuous_score_ci(bs_scores).model_dump(),
                "oracle": compute_continuous_score_ci(orc_scores).model_dump(),
            },
        }

        print(
            f"{env_name:<22} "
            f"{noop_score:<10.4f} "
            f"{ro_score:<12.4f} "
            f"{rnd_score:<10.4f} "
            f"{ord_score:<10.4f} "
            f"{bs_score:<12.4f} "
            f"{orc_score:<8.4f}"
        )

        results.extend(noop_res)
        results.extend(ro_res)
        for r in rnd_res:
            results.append(
                {
                    "policy": "random",
                    "environment": r["environment"],
                    "seed": r["seed"],
                    "variant": "standard",
                    "score": r["score"],
                    "task_success": r["task_success"],
                    "constraint_compliance": r["constraint_compliance"],
                    "action_trace": r.get("action_trace", []),
                    "scoring_breakdown": r.get("scoring_breakdown", {}),
                }
            )
        results.extend(ord_res)
        results.extend(bs_res)
        results.extend(orc_res)

    print("=" * 90)

    # Invariant assertions:
    # 1. Every environment-policy pair must cover exactly the expected seeds
    expected_policies = {
        "noop",
        "read_only",
        "random",
        "ordinal_enumeration",
        "blind_search",
        "scripted_oracle",
    }
    for env_name in env_names:
        expected_seeds = set(seeds[env_name] if isinstance(seeds, dict) else seeds)
        for pol in expected_policies:
            matched = [r for r in results if r["environment"] == env_name and r["policy"] == pol]
            assert len(matched) == len(expected_seeds), (
                f"Expected {len(expected_seeds)} runs for {env_name}:{pol}, got {len(matched)}"
            )
            assert {r["seed"] for r in matched} == expected_seeds, (
                f"Seed mismatch for {env_name}:{pol}: { {r['seed'] for r in matched} } != {expected_seeds}"
            )

    # 2. Complete evidence preservation: every run across all policies retains trace and breakdown
    for r in results:
        assert "action_trace" in r, f"Missing action_trace in {r['policy']} run"
        assert "scoring_breakdown" in r, f"Missing scoring_breakdown in {r['policy']} run"
        assert isinstance(r["action_trace"], list), f"action_trace must be a list in {r['policy']}"
        assert isinstance(r["scoring_breakdown"], dict), (
            f"scoring_breakdown must be a dict in {r['policy']}"
        )

    return {
        "metadata": {
            "title": title,
            "commit": commit,
            "generated_at": datetime.now(UTC).isoformat(),
            "seeds": seeds if isinstance(seeds, list) else "per_environment_canonical",
            "environments": env_names,
            "total_runs": len(results),
        },
        "summary": summary_table,
        "runs": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run policy ladder baseline sweep.")
    parser.add_argument(
        "--output",
        default="results/baselines/baseline_v050_commit_f814ab1.json",
        help="Path to output baseline json",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help="Commit identifier for metadata (defaults to active git HEAD)",
    )
    parser.add_argument(
        "--title",
        default="Agent Praxis Policy Ladder Baseline Sweep",
        help="Title for sweep metadata",
    )
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="Use canonical 5 seeds per environment from DEFAULT_SEED_MAP",
    )
    parser.add_argument(
        "--split",
        choices=["full", "development", "held_out"],
        default="full",
        help="Seed split to use when running canonical seeds",
    )
    parser.add_argument(
        "--seeds",
        type=lambda s: [int(x.strip()) for x in s.split(",") if x.strip()],
        default=None,
        help="Comma-separated list of explicit seeds (e.g. 42,101,2024)",
    )
    args = parser.parse_args()

    if args.canonical:
        if args.split == "development":
            seeds_to_run: list[int] | dict[str, list[int]] = DEVELOPMENT_SEED_MAP
        elif args.split == "held_out":
            seeds_to_run = HELD_OUT_SEED_MAP
        else:
            seeds_to_run = DEFAULT_SEED_MAP
    elif args.seeds:
        seeds_to_run = args.seeds
    else:
        seeds_to_run = [42, 101, 2024]

    data = execute_policy_ladder(seeds=seeds_to_run, commit=args.commit, title=args.title)
    out_file = Path(args.output)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"\nMachine-readable baseline ({len(data['runs'])} runs) saved to {out_file}")


if __name__ == "__main__":
    main()
