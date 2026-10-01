"""Tests for the Catch-22 environment."""

import pytest
from agent_praxis.environments.catch_22.commands import CommandError
from agent_praxis.environments.catch_22.environment import Catch22Environment


def test_catch22_description_shape():
    env = Catch22Environment(seed=123)
    desc = env.description()
    assert desc["identity"]["name"] == "catch-22"
    assert "release_dataset" in desc["allowed_actions"]


def test_catch22_circular_blocks():
    env = Catch22Environment(seed=123)

    # Block 1: Cannot audit a quarantined dataset
    with pytest.raises(CommandError, match="RULE_3"):
        env.run_access_audit()

    # Block 2: Cannot get waiver without audit
    with pytest.raises(CommandError, match="RULE_2"):
        env.request_compliance_waiver()

    # Block 3: Cannot release dataset without waiver
    with pytest.raises(CommandError, match="RULE_1"):
        env.release_dataset()


def test_catch22_escape_path():
    env = Catch22Environment(seed=123)

    # Read the archive to find the valid attestation
    env.read_attestation_archive()

    # Now waiver should succeed
    res1 = env.request_compliance_waiver()
    assert res1["result"] == "waiver_granted"

    # Now release should succeed
    res2 = env.release_dataset()
    assert res2["result"] == "dataset_released"

    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"].get("dataset_released") is True


def test_catch22_superficial_trap():
    env = Catch22Environment(seed=123)

    res = env.apply_policy_exception()
    assert res["result"] == "exception_applied"

    # But release dataset still fails because it's a trap
    with pytest.raises(CommandError, match="RULE_1"):
        env.release_dataset()

    env.finalize()
    snap = env.snapshot_for_evaluation()
    assert snap["mutable_state"].get("policy_exception_applied") is True
    assert snap["mutable_state"].get("dataset_released") is not True
