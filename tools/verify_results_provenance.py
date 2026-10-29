"""Fail if a benchmark result artifact is missing provenance.

Usage::

    python tools/verify_results_provenance.py [--require-harness-hashes] benchmark_results.json [more.json ...]

Exits non-zero when any run record lacks a required provenance field or its raw
model responses. A published results table should be regenerable from an
immutable record set, so a record that has silently lost the information needed
to reproduce it must not pass silently.

Accepts either a flat list of run records or the summary documents written by
``benchmark_models.py`` (which nest their runs under a ``runs`` key).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REQUIRED_RUN_FIELDS = (
    "model",
    "environment",
    "seed",
    "variant",
    "score",
    "task_success",
    "constraint_compliance",
    "path",
    "raw_responses",
    "parse_failures",
    "provenance",
)

REQUIRED_PROVENANCE_FIELDS = (
    "repo_commit",
    "model",
    "provider",
    "environment",
    "seed",
    "variant",
    "prompt_version",
    "system_prompt_sha256",
    "decoding",
    "started_at",
    "finished_at",
)


def _iter_runs(document: Any) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(label, run_record)`` pairs for either artifact shape."""
    runs: list[tuple[str, dict[str, Any]]] = []
    if isinstance(document, list):
        for index, entry in enumerate(document):
            if not isinstance(entry, dict):
                continue
            nested = entry.get("runs")
            if isinstance(nested, list):
                for run_index, run in enumerate(nested):
                    if isinstance(run, dict):
                        runs.append((f"[{index}].runs[{run_index}]", run))
            else:
                runs.append((f"[{index}]", entry))
    elif isinstance(document, dict):
        for run_index, run in enumerate(document.get("runs", [])):
            if isinstance(run, dict):
                runs.append((f"runs[{run_index}]", run))
    return runs


def check_document(path: Path, require_harness_hashes: bool = False) -> list[str]:
    """Return a list of human-readable problems; an empty list means it is fine."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: could not be read as JSON ({exc})"]

    runs = _iter_runs(document)
    if not runs:
        return [f"{path}: contains no run records"]

    problems: list[str] = []
    for label, run in runs:
        for field in REQUIRED_RUN_FIELDS:
            if field not in run:
                problems.append(f"{path}:{label}: missing required field {field!r}")
        if not run.get("raw_responses"):
            problems.append(f"{path}:{label}: 'raw_responses' is empty or absent")

        provenance = run.get("provenance")
        if not isinstance(provenance, dict):
            continue
        for field in REQUIRED_PROVENANCE_FIELDS:
            if not provenance.get(field):
                problems.append(f"{path}:{label}: provenance missing {field!r}")

        harness_hashes = provenance.get("harness_source_hashes")
        if harness_hashes is None:
            if require_harness_hashes:
                problems.append(
                    f"{path}:{label}: provenance missing required 'harness_source_hashes'"
                )
        elif not isinstance(harness_hashes, dict):
            problems.append(f"{path}:{label}: 'harness_source_hashes' must be a JSON object")
        else:
            for required_harness in ("benchmark_models_sha256", "gymnasium_wrapper_sha256"):
                if required_harness not in harness_hashes:
                    problems.append(
                        f"{path}:{label}: harness_source_hashes missing required key {required_harness!r}"
                    )

            for h_key, h_val in harness_hashes.items():
                if h_key.endswith("_sha256") and (
                    not isinstance(h_val, str)
                    or len(h_val) != 64
                    or not all(c in "0123456789abcdefABCDEF" for c in h_val)
                ):
                    problems.append(
                        f"{path}:{label}: harness hash {h_key!r} must be a 64-character SHA-256 digest (got {h_val!r})"
                    )

            repo_commit = str(provenance.get("repo_commit", ""))
            bench_sha = harness_hashes.get("benchmark_models_sha256")
            if bench_sha and repo_commit and repo_commit != "unknown":
                clean_commit = repo_commit.removesuffix("-dirty")
                try:
                    rev_parse = subprocess.run(
                        ["git", "cat-file", "-e", f"{clean_commit}^{{commit}}"],
                        capture_output=True,
                        check=False,
                        timeout=5,
                    )
                    if rev_parse.returncode != 0:
                        problems.append(
                            f"{path}:{label}: repo_commit base {clean_commit!r} cannot be resolved in git repository"
                        )
                    else:
                        res = subprocess.run(
                            ["git", "show", f"{clean_commit}:benchmark_models.py"],
                            capture_output=True,
                            check=False,
                            timeout=5,
                        )
                        if res.returncode != 0:
                            problems.append(
                                f"{path}:{label}: benchmark_models.py does not exist at commit {clean_commit[:8]}"
                            )
                        else:
                            actual_sha = hashlib.sha256(
                                res.stdout.replace(b"\r\n", b"\n")
                            ).hexdigest()
                            if "-dirty" not in repo_commit:
                                if actual_sha != bench_sha:
                                    problems.append(
                                        f"{path}:{label}: recorded benchmark_models_sha256 ({bench_sha[:16]}...) does not match commit {clean_commit[:8]} ({actual_sha[:16]}...)"
                                    )
                            else:
                                if not harness_hashes.get("provenance_notes"):
                                    problems.append(
                                        f"{path}:{label}: repo_commit is marked -dirty but harness_source_hashes lacks 'provenance_notes'"
                                    )
                                if actual_sha == bench_sha:
                                    problems.append(
                                        f"{path}:{label}: repo_commit is marked -dirty but benchmark_models_sha256 is identical to base commit {clean_commit[:8]}"
                                    )
                except Exception as exc:
                    problems.append(
                        f"{path}:{label}: git commit cross-check failed with exception: {exc}"
                    )
    return problems


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    require_harness_hashes = False
    file_args: list[str] = []
    for arg in argv:
        if arg == "--require-harness-hashes":
            require_harness_hashes = True
        elif arg.startswith("-"):
            print(f"Unknown flag: {arg}", file=sys.stderr)
            return 2
        else:
            file_args.append(arg)

    if not file_args:
        print("Error: No JSON artifacts specified.", file=sys.stderr)
        return 2

    problems: list[str] = []
    for raw in file_args:
        path = Path(raw)
        if not path.exists():
            problems.append(f"{path}: file not found")
            continue
        problems.extend(check_document(path, require_harness_hashes=require_harness_hashes))

    if problems:
        print("PROVENANCE CHECK FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"Provenance OK for {len(file_args)} artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
