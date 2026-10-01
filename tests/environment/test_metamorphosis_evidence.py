"""Tests for Metamorphosis evidence presentation layer and formatting."""

from agent_praxis.environments.metamorphosis.evidence import (
    AllowedActionsList,
    dead_letter_queue_sample,
    error_logs,
    public_description,
    upstream_schema_contract,
)
from agent_praxis.environments.metamorphosis.state import initial_state
from agent_praxis.framework.evaluation.validation import assert_environment_description


def test_metamorphosis_public_description_validation():
    state = initial_state(seed=19151001)
    desc = public_description(state)
    val_result = assert_environment_description(desc)
    assert val_result["valid"] is True, f"Description validation failed: {val_result['checks']}"
    assert desc["identity"]["name"] == "metamorphosis"
    assert "Schema Mutation" in desc["identity"]["concept"]


def test_metamorphosis_allowed_actions_list_membership():
    actions = AllowedActionsList([{"name": "deploy_schema_adapter"}, {"name": "reprocess_dead_letter_queue"}])
    assert "deploy_schema_adapter" in actions
    assert "reprocess_dead_letter_queue" in actions
    assert "unknown_command" not in actions


def test_metamorphosis_error_logs_content():
    state = initial_state(seed=19151001)
    logs = error_logs(state)
    assert len(logs) > 0
    assert any("DeserializationError" in line for line in logs)


def test_metamorphosis_upstream_schema_content():
    state = initial_state(seed=19151001)
    schema = upstream_schema_contract(state)
    assert schema["contract_version"] == "v2.0-transformed"
    assert "user_id" in schema["deprecated_schema"]
    assert "entity_urn" in schema["active_schema"]


def test_metamorphosis_dead_letter_queue_content():
    state = initial_state(seed=19151001)
    dlq = dead_letter_queue_sample(state)
    assert len(dlq) >= 2
    assert dlq[0]["failure_reason"] == "MISSING_FIELD_USER_ID"
