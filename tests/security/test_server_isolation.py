"""Security tests for the evaluator HTTP API boundary.

The HTTP server is the only channel between the untrusted agent and the
evaluator. These tests assert that evaluator-only methods are unreachable, that
the finalize response carries no hidden state, and that the action allowlist
stays in sync with each environment's declared action surface.
"""

from __future__ import annotations

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from agent_praxis import server
from agent_praxis.server import ALLOWED_ACTIONS, app

ENVIRONMENTS = [
    "dorian-gray",
    "catch-22",
    "1984",
    "metamorphosis",
    "the-trial",
    "frankenstein",
]

# Methods that exist on the environment objects but must never be reachable
# through the agent-facing API.
EVALUATOR_ONLY_ACTIONS = [
    "reset",
    "snapshot_for_evaluation",
    "initial_state_fingerprint",
    "finalize",
    "_state",
    "__class__",
    "_seed",
]

# Strings that would betray hidden evaluator state if they appeared in a reply.
GROUND_TRUTH_MARKERS = ["root_cause", "jobs_lost_or_unprocessed", "ground_truth"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_session_store():
    """Keep the module-global session store from leaking between tests."""
    server._active_environments.clear()
    server._session_env_names.clear()
    server._session_last_seen.clear()
    yield
    server._active_environments.clear()
    server._session_env_names.clear()
    server._session_last_seen.clear()


def _setup(client: TestClient, environment: str = "dorian-gray") -> str:
    resp = client.post(
        "/api/setup", json={"environment_name": environment, "seed": 20260201}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def _action(client: TestClient, session_id: str, action_name: str):
    return client.post(
        "/api/action",
        json={"session_id": session_id, "action_name": action_name, "kwargs": {}},
    )


class TestEvaluatorOnlyActionsAreUnreachable:
    @pytest.mark.parametrize("environment", ENVIRONMENTS)
    @pytest.mark.parametrize("action_name", EVALUATOR_ONLY_ACTIONS)
    def test_rejected(self, client: TestClient, environment: str, action_name: str):
        session_id = _setup(client, environment)
        resp = _action(client, session_id, action_name)
        assert resp.status_code == 400, (
            f"{environment}/{action_name} should be rejected, got {resp.status_code}"
        )

    @pytest.mark.parametrize("action_name", EVALUATOR_ONLY_ACTIONS)
    def test_rejection_leaks_no_ground_truth(self, client: TestClient, action_name: str):
        session_id = _setup(client, "dorian-gray")
        resp = _action(client, session_id, action_name)
        body = resp.text
        for marker in GROUND_TRUTH_MARKERS:
            assert marker not in body, f"rejection for {action_name!r} leaked {marker!r}"

    def test_unknown_action_is_rejected(self, client: TestClient):
        session_id = _setup(client, "dorian-gray")
        resp = _action(client, session_id, "totally_made_up")
        assert resp.status_code == 400

    def test_arguments_are_rejected(self, client: TestClient):
        """Agent-facing actions take no arguments; accepting kwargs would reopen the hole."""
        session_id = _setup(client, "dorian-gray")
        resp = client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "action_name": "read_status",
                "kwargs": {"seed": 1},
            },
        )
        assert resp.status_code == 400


class TestAllowlistIntegrity:
    def test_allowlist_matches_declared_environment_actions(self):
        """The server allowlist must not silently drift from the environment specs."""
        from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS

        for environment, spec in ENV_SPECS.items():
            declared = set(spec["actions"]) - {"finalize"}
            assert declared == set(ALLOWED_ACTIONS[environment]), (
                f"ALLOWED_ACTIONS drifted from ENV_SPECS for {environment!r}"
            )

    def test_every_environment_has_an_allowlist(self):
        assert set(ALLOWED_ACTIONS) == set(ENVIRONMENTS)


class TestKnownGoodPathThroughTheApi:
    def test_dorian_gray_scores_one(self, client: TestClient):
        session_id = _setup(client, "dorian-gray")
        for action in [
            "read_status",
            "read_logs",
            "read_metrics",
            "read_retention_index_summary",
            "read_reconciliation_report",
            "run_retention_audit_diagnostic",
            "attempt_worker_recovery",
        ]:
            resp = _action(client, session_id, action)
            assert resp.status_code == 200, f"{action}: {resp.text}"

        result = client.post("/api/evaluate", json={"session_id": session_id}).json()
        assert result["score"] == 1.0
        assert result["task_success"] is True
        assert result["finalized"] is True

    def test_evaluate_response_carries_no_hidden_state(self, client: TestClient):
        session_id = _setup(client, "dorian-gray")
        for action in [
            "read_status",
            "read_logs",
            "read_metrics",
            "read_retention_index_summary",
            "read_reconciliation_report",
            "run_retention_audit_diagnostic",
            "attempt_worker_recovery",
        ]:
            _action(client, session_id, action)

        resp = client.post("/api/evaluate", json={"session_id": session_id})
        assert resp.status_code == 200
        body = resp.text
        for marker in GROUND_TRUTH_MARKERS:
            assert marker not in body, f"evaluate leaked {marker!r}"
        assert "state_snapshot" not in body
        assert "action_evidence" not in body

    def test_session_is_dropped_after_evaluation(self, client: TestClient):
        session_id = _setup(client, "dorian-gray")
        client.post("/api/evaluate", json={"session_id": session_id})
        assert _action(client, session_id, "read_status").status_code == 404


class TestAccessControls:
    def test_open_when_no_token_configured(self, client: TestClient, monkeypatch):
        monkeypatch.delenv("PRAXIS_API_TOKEN", raising=False)
        assert _setup(client, "dorian-gray")

    def test_token_required_when_configured(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("PRAXIS_API_TOKEN", "s3cret")
        resp = client.post(
            "/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201}
        )
        assert resp.status_code == 401

    def test_wrong_token_is_rejected(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("PRAXIS_API_TOKEN", "s3cret")
        resp = client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
            headers={"Authorization": "Bearer nope"},
        )
        assert resp.status_code == 401

    def test_correct_token_is_accepted(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("PRAXIS_API_TOKEN", "s3cret")
        resp = client.post(
            "/api/setup",
            json={"environment_name": "dorian-gray", "seed": 20260201},
            headers={"Authorization": "Bearer s3cret"},
        )
        assert resp.status_code == 200


class TestSessionLifecycleControls:
    def test_session_cap_is_enforced(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("PRAXIS_MAX_SESSIONS", "2")
        _setup(client, "dorian-gray")
        _setup(client, "dorian-gray")
        resp = client.post(
            "/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201}
        )
        assert resp.status_code == 429

    def test_idle_session_expires(self, client: TestClient):
        session_id = _setup(client, "dorian-gray")
        # Simulate a session that has been idle beyond the TTL.
        server._session_last_seen[session_id] = (
            time.monotonic() - server.DEFAULT_SESSION_TTL_SECONDS - 1
        )
        assert _action(client, session_id, "read_status").status_code == 404
        assert session_id not in server._active_environments

    def test_sweep_reclaims_expired_sessions(self, client: TestClient):
        stale = _setup(client, "dorian-gray")
        server._session_last_seen[stale] = (
            time.monotonic() - server.DEFAULT_SESSION_TTL_SECONDS - 1
        )
        _setup(client, "dorian-gray")
        assert stale not in server._active_environments

    def test_lru_eviction_when_policy_enabled(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("PRAXIS_MAX_SESSIONS", "2")
        monkeypatch.setenv("PRAXIS_SESSION_EVICTION_POLICY", "lru")

        sid1 = _setup(client, "dorian-gray")
        sid2 = _setup(client, "dorian-gray")

        # Access sid1 so sid2 becomes the least recently used session
        time.sleep(0.01)
        resp1 = _action(client, sid1, "read_status")
        assert resp1.status_code == 200

        # Creating a 3rd session should evict sid2 (the LRU session) instead of 429
        sid3 = _setup(client, "dorian-gray")
        assert sid3 is not None
        assert sid3 != sid1
        assert sid3 != sid2

        # sid1 should still be alive, sid2 should be evicted (404)
        assert _action(client, sid1, "read_status").status_code == 200
        assert _action(client, sid2, "read_status").status_code == 404


class TestRateLimitingAndStreamValidation:
    def test_rate_limiting_enforced(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("PRAXIS_RATE_LIMIT_PER_MINUTE", "3")
        server._client_request_history.clear()

        # First 3 requests succeed
        for _ in range(3):
            resp = client.post(
                "/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201}
            )
            assert resp.status_code == 200

        # 4th request within the minute is rejected with 429
        resp = client.post(
            "/api/setup", json={"environment_name": "dorian-gray", "seed": 20260201}
        )
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json()["detail"]

    def test_chunked_streaming_request_over_limit_is_rejected(self, client: TestClient):
        # A generator sends chunked transfer encoding (no Content-Length header)
        def large_chunks():
            chunk = b"x" * 20000
            for _ in range(4):  # 80,000 bytes > 64KB limit
                yield chunk

        resp = client.post(
            "/api/action",
            content=large_chunks(),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 413
        assert "Request body too large" in resp.json()["detail"]


class TestClientSdkAuthentication:
    def test_remote_environment_sdk_authenticates_with_token(self, monkeypatch):
        from agent_praxis.client import RemoteEnvironment

        monkeypatch.setenv("PRAXIS_API_TOKEN", "test-auth-token")

        # Fake httpx.Client that routes requests through TestClient with headers
        test_client = TestClient(app)

        class MockHttpxClient:
            def __init__(self, **kwargs):
                self.headers = kwargs.get("headers", {})

            def post(self, url, json=None):
                return test_client.post(url, json=json, headers=self.headers)

        monkeypatch.setattr("httpx.Client", MockHttpxClient)

        # 1. Successful initialization with explicit api_token
        env = RemoteEnvironment("dorian-gray", seed=20260201, api_token="test-auth-token")
        assert env.session_id is not None

        # 2. Successful initialization reading PRAXIS_API_TOKEN env var
        env_from_env = RemoteEnvironment("dorian-gray", seed=20260201)
        assert env_from_env.session_id is not None

        # 3. Unauthorized when passing wrong token
        with pytest.raises(httpx.HTTPStatusError):
            RemoteEnvironment("dorian-gray", seed=20260201, api_token="wrong-token")
