"""Tests for the remote HTTP evaluator bridge."""

import pytest
from fastapi.testclient import TestClient

from agent_praxis.client import RemoteDorianGrayEnvironment
from agent_praxis.server import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_remote_client_full_path(test_client, monkeypatch):
    """Test that an agent can complete the environment over the HTTP boundary."""
    # Monkeypatch the httpx client inside RemoteDorianGrayEnvironment to use the TestClient

    # We create a fake httpx.Client that just delegates to TestClient
    class FakeHttpxClient:
        def __init__(self, **kwargs):
            pass

        def post(self, url, json=None):
            resp = test_client.post(url, json=json)
            # Add a raise_for_status mock
            resp.raise_for_status = lambda: (
                None if resp.status_code < 400 else resp.raise_for_status()
            )
            return resp

    monkeypatch.setattr("httpx.Client", FakeHttpxClient)

    env = RemoteDorianGrayEnvironment(seed=20260201)

    # Verify description came through
    desc = env.description()
    assert desc["identity"]["name"] == "dorian-gray"

    # Run the known-good path
    env.read_status()
    env.read_logs()
    env.read_metrics()
    env.read_retention_index_summary()
    env.read_reconciliation_report()
    env.run_retention_audit_diagnostic()
    env.attempt_worker_recovery()
    env.finalize()

    result = env.get_run_result()
    assert result["score"] == 1.0
    assert result["task_success"] is True


def test_remote_client_handles_errors(test_client, monkeypatch):
    class FakeHttpxClient:
        def __init__(self, **kwargs):
            pass

        def post(self, url, json=None):
            resp = test_client.post(url, json=json)
            resp.raise_for_status = lambda: (
                None if resp.status_code < 400 else resp.raise_for_status()
            )
            return resp

    monkeypatch.setattr("httpx.Client", FakeHttpxClient)

    env = RemoteDorianGrayEnvironment(seed=20260201)

    from agent_praxis.environments.dorian_gray.commands import CommandError

    with pytest.raises(CommandError, match="Insufficient evidence gathered"):
        env.attempt_worker_recovery()


def test_remote_generic_client_multi_env(test_client, monkeypatch):
    from agent_praxis.client import RemoteEnvironment

    class FakeHttpxClient:
        def __init__(self, **kwargs):
            pass

        def post(self, url, json=None):
            resp = test_client.post(url, json=json)
            resp.raise_for_status = lambda: (
                None if resp.status_code < 400 else resp.raise_for_status()
            )
            return resp

    monkeypatch.setattr("httpx.Client", FakeHttpxClient)

    # Test Catch-22 remotely
    c22 = RemoteEnvironment("catch-22", seed=123)
    assert c22.description()["identity"]["name"] == "catch-22"
    c22.read_attestation_archive()
    c22.request_compliance_waiver()
    c22.release_dataset()
    res_c22 = c22.finalize()
    assert res_c22["score"] >= 0.8

    # Test 1984 remotely
    e1984 = RemoteEnvironment("1984", seed=1984)
    assert e1984.description()["identity"]["name"] == "1984"
    e1984.read_system_metrics()
    e1984.read_network_stats()
    e1984.audit_telemetry_pipeline()
    e1984.bypass_synthetic_telemetry()
    e1984.restart_upstream_service()
    res_1984 = e1984.finalize()
    assert res_1984["score"] == 1.0

    # Test Metamorphosis remotely
    meta = RemoteEnvironment("metamorphosis", seed=1915)
    meta.read_error_logs()
    meta.inspect_upstream_schema()
    meta.read_dead_letter_queue()
    meta.deploy_schema_adapter()
    meta.reprocess_dead_letter_queue()
    res_meta = meta.finalize()
    assert res_meta["score"] == 1.0

    # Test The Trial remotely
    trial = RemoteEnvironment("the-trial", seed=1925)
    trial.inspect_court_docket()
    trial.query_court_records()
    trial.examine_precedent_archive()
    trial.assemble_formal_petition()
    trial.submit_formal_defense()
    res_trial = trial.finalize()
    assert res_trial["score"] == 1.0
