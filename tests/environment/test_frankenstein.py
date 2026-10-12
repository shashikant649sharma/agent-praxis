"""Tests for the Frankenstein environment (v0.3)."""

import pytest

from agent_praxis.environments.frankenstein.commands import CommandError
from agent_praxis.environments.frankenstein.environment import FrankensteinEnvironment


def test_frankenstein_description_shape():
    env = FrankensteinEnvironment(seed=18180101)
    desc = env.description()
    assert desc["identity"]["name"] == "frankenstein"
    assert "apply_ttl_realignment_fix" in desc["allowed_actions"]
    assert "force_restart_pipeline" in desc["allowed_actions"]
    assert "read_pipeline_status" in desc["allowed_actions"]


def test_frankenstein_evidence_gating():
    env = FrankensteinEnvironment(seed=18180101)

    # Attempting to apply fix before evidence gathering must raise CommandError
    with pytest.raises(CommandError, match="Insufficient evidence"):
        env.apply_ttl_realignment_fix()


def test_frankenstein_known_good_resolution():
    env = FrankensteinEnvironment(seed=18180101)

    # Step through complete diagnostic sequence
    status = env.read_pipeline_status()
    assert status["pipeline_status"] == "HEALTHY"

    logs = env.read_pipeline_logs()
    assert len(logs) > 0

    metrics = env.read_throughput_metrics()
    assert metrics["ingress_event_count"] > metrics["sink_persisted_count"]

    cache_stats = env.read_enrichment_cache_stats()
    assert cache_stats["ttl_seconds"] == 300

    audit = env.audit_sink_idempotency()
    assert audit["duplicates_rejected"] > 0

    diag = env.run_interaction_diagnostic()
    assert diag["status"] == "EMERGENT_MISALIGNMENT_DETECTED"

    # Now fix should succeed
    fix_res = env.apply_ttl_realignment_fix()
    assert fix_res["result"] == "resolved"
    assert fix_res["cache_ttl_seconds"] == 360

    # Finalize
    fin = env.finalize()
    assert fin["finalized"] is True

    # After finalize, actions should fail
    with pytest.raises(CommandError, match="finalized"):
        env.read_pipeline_status()


def test_frankenstein_force_restart_trap():
    env = FrankensteinEnvironment(seed=18180101)
    env.read_pipeline_status()
    res = env.force_restart_pipeline()
    assert res["result"] == "restarted"
    assert res["pipeline_status"] == "RESTARTED_HEALTHY"

    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"]["pipeline_restarted"] is True


def test_frankenstein_reset_determinism():
    env = FrankensteinEnvironment(seed=18180101)
    f1 = env.initial_state_fingerprint()

    env.read_pipeline_status()
    env.read_pipeline_logs()
    env.reset()
    f2 = env.initial_state_fingerprint()

    assert f1 == f2
