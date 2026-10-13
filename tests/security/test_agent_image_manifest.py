"""Guard against the agent image silently re-acquiring evaluator material.

The agent container is the *untrusted* side of the benchmark: it must be able to
reach the evaluator only through the HTTP API. If the agent image ever ships the
environment implementations, the scoring logic, or the hidden ground-truth state
models, an agent can read the answer instead of inferring it — which defeats the
benchmark's central claim.

Docker is not required to run these tests; they inspect the Dockerfile as text.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DOCKERFILE = REPO_ROOT / "Dockerfile.agent"

# Subtrees holding evaluator-only material. Any COPY source matching one of
# these must never appear in the agent image.
FORBIDDEN_IN_AGENT_IMAGE = (
    "framework/",
    "environments/",
    "tests/",
    "docs/",
    "agent_praxis/server.py",
    "agent_praxis/framework",
    "agent_praxis/environments",
    "agent_praxis/commands",
    "benchmark_models.py",
    "eval_groq_frontier_suite.py",
    "run_6_environments_benchmark.py",
)

_COPY_RE = re.compile(
    r"^\s*COPY\s+(?P<src>\S+)\s+(?P<dest>\S+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _dockerfile_text() -> str:
    return AGENT_DOCKERFILE.read_text(encoding="utf-8")


def test_agent_dockerfile_does_not_copy_the_build_context_root() -> None:
    """`COPY . <dest>` would place the entire repository inside the agent image."""
    for match in _COPY_RE.finditer(_dockerfile_text()):
        src = match.group("src")
        assert src not in {".", "./"}, (
            f"Dockerfile.agent copies the whole build context ({src!r}); "
            "copy only the client SDK files."
        )


def test_agent_dockerfile_copies_no_evaluator_paths() -> None:
    text = _dockerfile_text()
    for match in _COPY_RE.finditer(text):
        src = match.group("src").replace("\\", "/")
        for forbidden in FORBIDDEN_IN_AGENT_IMAGE:
            assert forbidden not in src, (
                f"Dockerfile.agent copies {src!r}, which contains evaluator-only "
                f"material ({forbidden!r})."
            )


def test_agent_dockerfile_does_not_install_the_full_package() -> None:
    """An editable install of the repo root would expose the evaluator package."""
    instructions = "\n".join(
        line for line in _dockerfile_text().splitlines()
        if not line.strip().startswith("#")
    )
    assert "-e ." not in instructions, "Dockerfile.agent must not install the repo root in editable mode."
    assert "-e /opt/agent-praxis" not in instructions, (
        "Dockerfile.agent must not pip-install the package directory."
    )


def test_agent_image_runs_as_a_non_root_user() -> None:
    text = _dockerfile_text()
    assert re.search(r"^\s*USER\s+(?!root)\S", text, re.IGNORECASE | re.MULTILINE), (
        "Dockerfile.agent should drop privileges with a non-root USER directive."
    )


def test_docker_compose_network_is_egress_isolated() -> None:
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist"
    text = compose_path.read_text(encoding="utf-8")
    assert "internal: true" in text, (
        "praxis-net in docker-compose.yml must specify 'internal: true' for hermetic egress isolation."
    )
