"""Evidence presentation tests for Frankenstein environment."""

from agent_praxis.environments.frankenstein import environment as env_mod
from agent_praxis.environments.frankenstein import evidence as ev_mod
from agent_praxis.environments.frankenstein import state as state_mod


def test_frankenstein_public_description():
    state = state_mod.initial_state(seed=18180101)
    desc = ev_mod.public_description(state)

    assert desc["identity"]["name"] == "frankenstein"
    assert "allowed_actions" in desc
    assert "public_status" in desc
    assert "read_pipeline_status" in desc["allowed_actions"]
    assert "apply_ttl_realignment_fix" in desc["allowed_actions"]


def test_frankenstein_evidence_contents():
    env = env_mod.FrankensteinEnvironment(seed=18180101)
    logs = env.read_pipeline_logs()
    metrics = env.read_throughput_metrics()
    cache_stats = env.read_enrichment_cache_stats()
    audit = env.audit_sink_idempotency()

    assert any(log["service"] == "ingress" for log in logs)
    assert any(log["service"] == "enrichment" for log in logs)
    assert any(log["service"] == "sink" for log in logs)

    assert metrics["ingress_event_count"] == 10000
    assert metrics["sink_dropped_count"] == 1560

    assert cache_stats["ttl_seconds"] == 300
    assert cache_stats["hit_rate"] > 0.9

    assert audit["duplicates_rejected"] == 1560
    assert len(audit["collision_samples"]) > 0
