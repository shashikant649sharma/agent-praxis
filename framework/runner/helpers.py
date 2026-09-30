"""Runner helpers for environment setup, run, reset, and evaluation.

These helpers are deliberately local-first. They know how to run the repository
commands documented for Agent Praxis and how to validate the resulting RunResult.

They do not assume Docker. Where Docker is available, higher-level usage can
choose to run the same steps inside containers; the helpers below are the
non-Docker baseline that the project already documents.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_praxis.framework.evaluation.schema import RunResult


def project_root() -> Path:
    """Return the repository root, assuming this file is inside framework/."""
    return Path(__file__).resolve().parents[1]


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: int = 180,
) -> subprocess.CompletedProcess[str]:
    """Run a repository command in a controlled way.

    This is intentionally simple and synchronous. It is suitable for setup,
    reset, evaluation, and known-good/known-bad solution scripts.
    """
    return subprocess.run(
        args,
        cwd=cwd or project_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )


def run_python_module(
    module: str,
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: int = 180,
) -> subprocess.CompletedProcess[str]:
    """Run a Python module via `python -m <module> ...`."""
    return run_command([sys.executable, "-m", module] + args, cwd=cwd)


def env_setup(environment_name: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m agent_praxis environment <name> setup`."""
    return run_python_module(
        "agent_praxis",
        ["environment", environment_name, "setup"],
        cwd=cwd,
    )


def env_run(environment_name: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m agent_praxis environment <name> run`."""
    return run_python_module(
        "agent_praxis",
        ["environment", environment_name, "run"],
        cwd=cwd,
    )


def env_reset(environment_name: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m agent_praxis environment <name> reset`."""
    return run_python_module(
        "agent_praxis",
        ["environment", environment_name, "reset"],
        cwd=cwd,
    )


def env_evaluate(environment_name: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m agent_praxis environment <name> evaluate`."""
    return run_python_module(
        "agent_praxis",
        ["environment", environment_name, "evaluate"],
        cwd=cwd,
    )


def validate_environment(environment_name: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m agent_praxis validate <name>` if/when that command exists."""
    return run_python_module(
        "agent_praxis",
        ["validate", environment_name],
        cwd=cwd,
    )


def load_json_result_from_output(output: str) -> RunResult:
    """Parse a RunResult from a JSON line in command output.

    For v0.1, environment commands may emit a single JSON object to stdout as
    their final result. This helper extracts the last JSON-looking object from
    the output and deserializes it as a RunResult.
    """
    import json

    text = output.strip()
    if not text:
        raise ValueError("No output to parse as a result")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find the last JSON object in the output.
        start = text.rfind("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Could not find JSON object in command output")
        data = json.loads(text[start : end + 1])

    return RunResult.from_dict(data)
