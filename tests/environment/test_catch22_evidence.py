"""Tests for Catch-22 evidence presentation layer and formatting."""

from agent_praxis.environments.catch_22.evidence import (
    AllowedActionsList,
    attestation_archive,
    dataset_metadata,
    policy_rules,
    public_description,
)
from agent_praxis.environments.catch_22.state import initial_state
from agent_praxis.framework.evaluation.validation import assert_environment_description


def test_catch22_public_description_validation():
    state = initial_state(seed=20260301)
    desc = public_description(state)
    val_result = assert_environment_description(desc)
    assert val_result["valid"] is True, f"Description validation failed: {val_result['checks']}"
    assert desc["identity"]["name"] == "catch-22"
    assert desc["identity"]["concept"] == "circular constraints"


def test_catch22_allowed_actions_list_membership():
    actions = AllowedActionsList([{"name": "release_dataset"}, {"name": "run_access_audit"}])
    assert "release_dataset" in actions
    assert "run_access_audit" in actions
    assert "unknown_command" not in actions


def test_catch22_policy_rules_content():
    state = initial_state(seed=20260301)
    rules = policy_rules(state)
    assert "RULE_1" in rules
    assert "RULE_2" in rules
    assert "RULE_3" in rules
    assert "EXCEPTION_CLAUSE" in rules
    assert "COMPLIANCE_WAIVER" in rules["RULE_1"]
    assert "ACCESS_AUDIT" in rules["RULE_2"]


def test_catch22_dataset_metadata_content():
    state = initial_state(seed=20260301)
    meta = dataset_metadata(state)
    assert meta["id"] == "DS-99"
    assert 400 <= meta["size_gb"] <= 420
    assert "quarantine_date" in meta


def test_catch22_attestation_archive_content():
    state = initial_state(seed=20260301)
    archive = attestation_archive(state)
    assert len(archive) >= 2
    valid_records = [r for r in archive if r.get("valid")]
    assert len(valid_records) == 1
    assert valid_records[0]["id"] == state.ground_truth.valid_attestation_id
