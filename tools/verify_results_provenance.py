"""Fail if a benchmark result artifact is missing provenance.

Usage::

    python tools/verify_results_provenance.py benchmark_results.json [more.json ...]

Exits non-zero when any run record lacks a required provenance field or its raw
model responses. A published results table should be regenerable from an
immutable record set, so a record that has silently lost the information needed
to reproduce it must not pass silently.

Accepts either a flat list of run records or the summary documents written by
``benchmark_models.py`` (which nest their runs under a ``runs`` key).
"""

from __future__ import annotations

import json
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


def check_document(path: Path) -> list[str]:
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
    return problems


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    problems: list[str] = []
    for raw in argv:
        path = Path(raw)
        if not path.exists():
            problems.append(f"{path}: file not found")
            continue
        problems.extend(check_document(path))

    if problems:
        print("PROVENANCE CHECK FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"Provenance OK for {len(argv)} artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
