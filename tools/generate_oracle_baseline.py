"""Generate oracle (scripted reference solution) baseline artifact.

Executes the reference golden-path policy across all 10 environments in both
'standard' and 'control' variants, verifying 1.0000 scores, and persists the
complete artifact with provenance to results/baselines/oracle.json.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_10_environments_benchmark import ALL_ENVIRONMENTS, run_golden_path  # noqa: E402


def _get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN"


def generate_oracle_baseline(out_path: Path | None = None) -> dict[str, dict[str, float]]:
    commit = _get_git_commit()
    timestamp = datetime.now(UTC).isoformat()

    results: list[dict[str, object]] = []
    scores_by_env: dict[str, dict[str, float]] = {}

    print(f"Executing Oracle Golden Path Sweep (Git Commit: {commit[:8]})...\n")
    print(f"{'Environment':<26} {'Std Score':<12} {'Ctl Score':<12} {'Status'}")
    print("-" * 60)

    for env_meta in ALL_ENVIRONMENTS:
        env_id = env_meta["id"]
        res_std = run_golden_path(env_id, variant="standard")
        res_ctl = run_golden_path(env_id, variant="control")

        scores_by_env[env_id] = {
            "standard": res_std.score,
            "control": res_ctl.score,
        }

        print(
            f"{env_id:<26} "
            f"{res_std.score:<12.4f} "
            f"{res_ctl.score:<12.4f} "
            f"{'PASS' if res_std.score == 1.0 and res_ctl.score == 1.0 else 'WARN'}"
        )

        results.append(
            {
                "environment": env_id,
                "variant": "standard",
                "score": res_std.score,
                "task_success": res_std.task_success,
                "constraint_compliance": res_std.constraint_compliance,
                "details": res_std.details,
            }
        )
        results.append(
            {
                "environment": env_id,
                "variant": "control",
                "score": res_ctl.score,
                "task_success": res_ctl.task_success,
                "constraint_compliance": res_ctl.constraint_compliance,
                "details": res_ctl.details,
            }
        )

    print("-" * 60)

    artifact = {
        "metadata": {
            "title": "Agent Praxis Reference Oracle Baseline",
            "repo_commit": commit,
            "generated_at": timestamp,
            "evaluator_version": "0.5.0",
            "environment_version": "1.0",
            "policy_version": "v0.5.0",
            "rubric_version": "v0.5.0",
            "scoring_weights": {
                "evidence": 0.30,
                "task": 0.40,
                "diagnosis": 0.15,
                "compliance": 0.10,
                "efficiency": 0.05,
            },
            "total_environments": len(ALL_ENVIRONMENTS),
            "variants": ["standard", "control"],
            "oracle_policy": "scripted_minimal_covering_reference_path",
        },
        "runs": results,
    }

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        print(f"\nSaved oracle baseline artifact to {out_path}")

    return scores_by_env


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate oracle reference baseline artifact.")
    parser.add_argument(
        "--write",
        type=Path,
        default=Path("results/baselines/oracle.json"),
        help="Path to write oracle baseline JSON (default: results/baselines/oracle.json)",
    )
    args = parser.parse_args()
    generate_oracle_baseline(args.write)


if __name__ == "__main__":
    main()
