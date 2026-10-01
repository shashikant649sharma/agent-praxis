"""Tests for Catch-22 commands, categories, and allowlist validation."""

from dataclasses import FrozenInstanceError

import pytest

from agent_praxis.environments.catch_22.commands import (
    ALLOWED_COMMANDS,
    COMMAND_LABEL_TO_INDEX,
    AllowedCommand,
    CommandCategory,
    CommandError,
    describe_allowed_commands,
    describe_environment_description_command_index,
    validate_command_name,
)


def test_catch22_allowed_commands_surface():
    assert len(ALLOWED_COMMANDS) == 10
    names = [cmd.name for cmd in ALLOWED_COMMANDS]
    assert "read_environment_description" in names
    assert "read_status" in names
    assert "read_policy_rules" in names
    assert "read_dataset_metadata" in names
    assert "read_attestation_archive" in names
    assert "run_access_audit" in names
    assert "request_compliance_waiver" in names
    assert "apply_policy_exception" in names
    assert "release_dataset" in names
    assert "finalize" in names


def test_catch22_command_categories():
    categories = {cmd.category for cmd in ALLOWED_COMMANDS}
    assert CommandCategory.read in categories
    assert CommandCategory.inspect in categories
    assert CommandCategory.act in categories


def test_catch22_allowed_command_immutability():
    cmd = ALLOWED_COMMANDS[0]
    assert isinstance(cmd, AllowedCommand)
    with pytest.raises(FrozenInstanceError):
        cmd.name = "new_name"  # type: ignore[misc]


def test_catch22_describe_allowed_commands():
    desc = describe_allowed_commands()
    assert isinstance(desc, list)
    assert len(desc) == 10
    first = desc[0]
    assert set(first.keys()) == {
        "category",
        "name",
        "description",
        "restricted_target",
        "note",
    }


def test_catch22_validate_command_name():
    validate_command_name("release_dataset")
    validate_command_name("request_compliance_waiver")

    with pytest.raises(CommandError, match="Unknown command: 'delete_database'"):
        validate_command_name("delete_database")


def test_catch22_command_indices_match():
    assert describe_environment_description_command_index() == 0
    for cmd in ALLOWED_COMMANDS:
        assert cmd.name in COMMAND_LABEL_TO_INDEX
