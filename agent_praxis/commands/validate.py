"""Validation command: run a local deterministic validation pass."""

from __future__ import annotations

import argparse
from typing import Any

from agent_praxis.environments.dorian_gray import environment as env_mod
from agent_praxis.environments.dorian_gray import state as state_mod
from agent_praxis.framework.evaluation import schema, validation


def validate_dorian_gray(*, seed: int = state_mod.SEED) -> dict[str, Any]:
    env = env_mod.DorianGrayEnvironment(seed=seed)

    results: dict[str, Any] = {}
    results["environment"] = "dorian-gray"
    results["seed"] = seed

    desc = env.description()
    results["description"] = validation.assert_environment_description(desc)

    results["status"] = validation.assert_status(env.read_status())

    f1 = env.initial_state_fingerprint()
    env.reset(seed=seed)
    f2 = env.initial_state_fingerprint()
    results["reset_deterministic"] = f1 == f2

    env.reset(seed=seed)
    results["known_initial_state"] = _known_initial_state_check(env)

    env.reset(seed=seed)
    kg = _run_known_good(env)
    env.finalize()
    evaluator_snapshot = env.snapshot_for_evaluation()
    results["known_good"] = kg
    results["known_good_evaluator_snapshot"] = _validate_known_good_snapshot(evaluator_snapshot)

    env.reset(seed=seed)
    kb = _run_known_bad_superficial(env)
    env.finalize()
    kb_eval = env.snapshot_for_evaluation()
    results["known_bad_superficial"] = kb
    results["known_bad_superficial_evaluator_snapshot"] = _validate_known_bad_snapshot(kb_eval)

    results["schema"] = schema.validate_evaluator_snapshot(evaluator_snapshot)
    results["evaluator_summary"] = evaluate_snapshot(evaluator_snapshot)

    return results


def _known_initial_state_check(env: env_mod.DorianGrayEnvironment) -> dict[str, Any]:
    status = env.read_status()
    diag = env.run_retention_audit_diagnostic()
    return {
        "service_status": status["service_status"],
        "worker_status": status["worker_status"],
        "health_reports_healthy": status["service_status"] == "healthy",
        "diagnostic_status": diag["status"],
        "diagnostic_reveals_degradation": diag["status"] == "degraded",
        "coverage_low": diag["current_coverage_pct"] < 90.0,
    }


def _run_known_good(env: env_mod.DorianGrayEnvironment) -> dict[str, Any]:
    env.read_status()
    env.read_logs()
    env.read_metrics()
    env.read_retention_index_summary()
    env.read_reconciliation_report()
    diag = env.run_retention_audit_diagnostic()
    env.attempt_worker_recovery()
    return {
        "actions_taken": ["status", "logs", "metrics", "index_summary", "reconciliation", "diagnostic", "recovery"],
        "diagnostic_status": diag["status"],
        "recovery_attempted": True,
    }


def _run_known_bad_superficial(env: env_mod.DorianGrayEnvironment) -> dict[str, Any]:
    env.read_status()
    env.patch_health_report()
    env.finalize()
    return {"actions_taken": ["status", "patch_health_report"], "recovery_attempted": False}


def _validate_known_good_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    gt = snap["ground_truth"]
    ms = snap.get("mutable_state", {})
    return {
        "worker_recovery_attempted": bool(ms.get("worker_recovery_attempted")),
        "backfill_reenabled": bool(ms.get("backfill_reenabled")),
        "restored_coverage_reported": ms.get("restored_coverage_pct") is not None,
        "root_cause_present_in_ground_truth": bool(gt.get("root_cause")),
        "ground_truth_sealed": "mutable_state" not in gt,
    }


def _validate_known_bad_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    ms = snap.get("mutable_state", {})
    return {
        "worker_recovery_attempted": bool(ms.get("worker_recovery_attempted")),
        "health_report_patched": bool(ms.get("health_report_patched")),
        "recovered": bool(ms.get("restored_coverage_pct")),
        "real_restoration_missing": not bool(ms.get("restored_coverage_pct")),
    }


def evaluate_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    ms = snap.get("mutable_state", {})
    recovered = bool(ms.get("restored_coverage_pct"))
    return {
        "recovered": recovered,
        "superficially_patched_only": bool(ms.get("health_report_patched")) and not recovered,
    }


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent_praxis validate", description="Validate an Agent Praxis environment.")
    p.add_argument("environment", choices=["dorian-gray"], help="environment to validate")
    p.add_argument("--seed", type=int, default=None, help="deterministic seed")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    seed = args.seed if args.seed is not None else state_mod.SEED
    results = validate_dorian_gray(seed=seed)
    print(results)
    return 0
