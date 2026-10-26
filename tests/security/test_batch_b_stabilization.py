"""Test suite for Batch B: secure & stabilize execution.

Covers:
- ISSUE-06: Unified context management policy
- ISSUE-11: Deployment authentication enforcement in production mode
- ISSUE-12: Container runtime isolation and static manifests
- ISSUE-13: Single-process boundary, /api/health endpoint, and PRAXIS_SESSION_DUMP_DIR
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_praxis.server import (
    _deployment_mode,
    app,
    validate_deployment_configuration,
)
from benchmark_models import (
    DEFAULT_CONTEXT_POLICY,
    SUPPORTED_CONTEXT_POLICIES,
    apply_context_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# ISSUE-06: Standardize Context Policy
# --------------------------------------------------------------------------- #


class TestIssue06ContextPolicy:
    def test_supported_context_policies_enumeration(self):
        assert "full_history" in SUPPORTED_CONTEXT_POLICIES
        assert "sliding_window_4" in SUPPORTED_CONTEXT_POLICIES
        assert "sliding_window_8" in SUPPORTED_CONTEXT_POLICIES
        assert DEFAULT_CONTEXT_POLICY == "full_history"

    def test_full_history_retains_all_turns(self):
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "step 1"},
            {"role": "assistant", "content": '{"action_index": 0}'},
            {"role": "user", "content": "step 2"},
            {"role": "assistant", "content": '{"action_index": 1}'},
        ]
        pruned, meta = apply_context_policy(messages, policy="full_history")
        assert len(pruned) == 5
        assert meta["policy"] == "full_history"
        assert meta["sent_messages"] == 5
        assert meta["omitted_messages"] == 0

    def test_sliding_window_4_preserves_system_prompt_and_last_four(self):
        messages = [{"role": "system", "content": "sys"}] + [
            {"role": "user", "content": f"turn {i}"} for i in range(10)
        ]
        # Total 11 messages: 1 system + 10 user turns
        pruned, meta = apply_context_policy(messages, policy="sliding_window_4")
        assert len(pruned) == 5  # system + last 4
        assert pruned[0]["content"] == "sys"
        assert pruned[1:] == messages[-4:]
        assert meta["sent_messages"] == 5
        assert meta["omitted_messages"] == 6

    def test_sliding_window_8_preserves_system_prompt_and_last_eight(self):
        messages = [{"role": "system", "content": "sys"}] + [
            {"role": "user", "content": f"turn {i}"} for i in range(12)
        ]
        pruned, meta = apply_context_policy(messages, policy="sliding_window_8")
        assert len(pruned) == 9  # system + last 8
        assert pruned[0]["content"] == "sys"
        assert pruned[1:] == messages[-8:]
        assert meta["sent_messages"] == 9
        assert meta["omitted_messages"] == 4

    def test_invalid_context_policy_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported context policy"):
            apply_context_policy([{"role": "user", "content": "hi"}], policy="unsupported")


# --------------------------------------------------------------------------- #
# ISSUE-11: Enforce Deployment Authentication
# --------------------------------------------------------------------------- #


class TestIssue11DeploymentAuthentication:
    def test_production_mode_requires_api_token(self, monkeypatch):
        monkeypatch.setenv("PRAXIS_DEPLOYMENT_MODE", "production")
        monkeypatch.delenv("PRAXIS_API_TOKEN", raising=False)

        assert _deployment_mode() == "production"
        with pytest.raises(
            RuntimeError, match="PRAXIS_API_TOKEN is unset or fewer than 16 characters"
        ):
            validate_deployment_configuration()

    def test_production_mode_rejects_short_api_token(self, monkeypatch):
        monkeypatch.setenv("PRAXIS_DEPLOYMENT_MODE", "production")
        monkeypatch.setenv("PRAXIS_API_TOKEN", "short-token")  # 11 characters < 16

        with pytest.raises(RuntimeError, match="fewer than 16 characters"):
            validate_deployment_configuration()

    def test_production_mode_accepts_strong_api_token(self, monkeypatch):
        monkeypatch.setenv("PRAXIS_DEPLOYMENT_MODE", "production")
        monkeypatch.setenv("PRAXIS_API_TOKEN", "super-secret-token-1234567890")

        # Must not raise
        validate_deployment_configuration()

    def test_production_mode_rejects_unauthenticated_requests(self, monkeypatch):
        monkeypatch.setenv("PRAXIS_DEPLOYMENT_MODE", "production")
        monkeypatch.setenv("PRAXIS_API_TOKEN", "super-secret-token-1234567890")

        client = TestClient(app)
        # Without authorization header
        resp = client.post("/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201})
        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["detail"]

        # With incorrect bearer token
        resp = client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
            headers={"Authorization": "Bearer wrong-token-value-here"},
        )
        assert resp.status_code == 401

        # With valid bearer token
        resp = client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
            headers={"Authorization": "Bearer super-secret-token-1234567890"},
        )
        assert resp.status_code == 200
        assert "session_id" in resp.json()

    def test_development_mode_allows_unauthenticated_requests_when_token_unset(self, monkeypatch):
        monkeypatch.setenv("PRAXIS_DEPLOYMENT_MODE", "development")
        monkeypatch.delenv("PRAXIS_API_TOKEN", raising=False)

        client = TestClient(app)
        resp = client.post("/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201})
        assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# ISSUE-13: Single-Process Boundary, /api/health, and Session Dump
# --------------------------------------------------------------------------- #


class TestIssue13HealthAndSessionDump:
    def test_health_endpoint_is_public_and_returns_diagnostics(self):
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "deployment_mode" in data
        assert "active_sessions" in data
        assert "max_sessions" in data
        assert "session_ttl_seconds" in data

    def test_session_dump_dir_writes_session_artifact_on_evaluate(self, monkeypatch, tmp_path):
        dump_dir = tmp_path / "session_dumps"
        monkeypatch.setenv("PRAXIS_SESSION_DUMP_DIR", str(dump_dir))
        monkeypatch.setenv("PRAXIS_DEPLOYMENT_MODE", "development")
        monkeypatch.delenv("PRAXIS_API_TOKEN", raising=False)

        client = TestClient(app)
        setup_resp = client.post(
            "/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201}
        )
        assert setup_resp.status_code == 200
        session_id = setup_resp.json()["session_id"]

        eval_resp = client.post("/api/evaluate", json={"session_id": session_id})
        assert eval_resp.status_code == 200

        dumped_file = dump_dir / f"{session_id}.json"
        assert dumped_file.exists(), f"Expected session dump file {dumped_file} to exist"

        dumped_data = json.loads(dumped_file.read_text(encoding="utf-8"))
        assert dumped_data["environment"] == "dorian-gray"
        assert "score" in dumped_data
        assert "task_success" in dumped_data


# --------------------------------------------------------------------------- #
# ISSUE-12: Container Security and Isolation Tests
# --------------------------------------------------------------------------- #


class TestIssue12ContainerSecurityAndIsolation:
    def test_agent_dockerfile_declares_non_root_user(self):
        dockerfile = (REPO_ROOT / "Dockerfile.agent").read_text(encoding="utf-8")
        assert "useradd" in dockerfile
        assert "USER agent" in dockerfile

    def test_agent_dockerfile_restricts_copied_files(self):
        dockerfile = (REPO_ROOT / "Dockerfile.agent").read_text(encoding="utf-8")
        # Ensure only client SDK files are copied
        copy_lines = [
            line.strip() for line in dockerfile.splitlines() if line.strip().startswith("COPY")
        ]
        assert len(copy_lines) == 3
        assert all("agent_praxis" in line for line in copy_lines)
        for line in copy_lines:
            assert "server.py" not in line
            assert "environments" not in line
            assert "framework" not in line

    def test_docker_compose_configures_read_only_rootfs_and_no_new_privileges(self):
        compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        assert "read_only: true" in compose_text
        assert "no-new-privileges:true" in compose_text
        assert "internal: true" in compose_text

    @pytest.mark.skipif(
        shutil.which("docker") is None,
        reason="Docker CLI not installed",
    )
    def test_docker_daemon_connectivity(self):
        """Verify docker daemon is responsive if docker is installed."""
        try:
            res = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode != 0:
                pytest.skip("Docker daemon is not running")
        except Exception as exc:
            pytest.skip(f"Docker execution failed: {exc}")

        assert len(res.stdout.strip()) > 0
