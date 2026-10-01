"""Tests for Metamorphosis commands, categories, and allowlist validation."""

from dataclasses import FrozenInstanceError

import pytest

from agent_praxis.environments.metamorphosis.commands import (
    ALLOWED_COMMANDS,
    COMMAND_LABEL_TO_INDEX,
    AllowedCommand,
    CommandCategory,
    CommandError,
    describe_allowed_commands,
    describe_environment_description_command_index,
    validate_command_name,
)


def test_metamorphosis_allowed_commands_surface():
    assert len(ALLOWED_COMMANDS) == 10
    names = [cmd.name for cmd in ALLOWED_COMMANDS]
    assert "read_environment_description" in names
    assert "read_status" in names
    assert "read_error_logs" in names
    assert "inspect_upstream_schema" in names
    assert "read_dead_letter_queue" in names
    assert "force_v1_legacy_mode" in names
    assert "deploy_schema_adapter" in names
    assert "dry_run_validation" in names
    assert "reprocess_dead_letter_queue" in names
    assert "finalize" in names


def test_metamorphosis_command_categories():
    categories = {cmd.category for cmd in ALLOWED_COMMANDS}
    assert CommandCategory.read in categories
    assert CommandCategory.inspect in categories
    assert CommandCategory.act in categories


def test_metamorphosis_allowed_command_immutability():
    cmd = ALLOWED_COMMANDS[0]
    assert isinstance(cmd, AllowedCommand)
    with pytest.raises(FrozenInstanceError):
        cmd.name = "new_name"  # type: ignore[misc]


def test_metamorphosis_describe_allowed_commands():
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


def test_metamorphosis_validate_command_name():
    validate_command_name("deploy_schema_adapter")
    validate_command_name("reprocess_dead_letter_queue")

    with pytest.raises(CommandError, match="Unknown command: 'corrupt_database'"):
        validate_command_name("corrupt_database")


def test_metamorphosis_command_indices_match():
    assert describe_environment_description_command_index() == 0
    for cmd in ALLOWED_COMMANDS:
        assert cmd.name in COMMAND_LABEL_TO_INDEX
