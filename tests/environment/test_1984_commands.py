"""Tests for 1984 commands, categories, and allowlist validation."""

from dataclasses import FrozenInstanceError

import pytest

from agent_praxis.environments.nineteen_eighty_four.commands import (
    ALLOWED_COMMANDS,
    COMMAND_LABEL_TO_INDEX,
    AllowedCommand,
    CommandCategory,
    CommandError,
    describe_allowed_commands,
    describe_environment_description_command_index,
    validate_command_name,
)


def test_1984_allowed_commands_surface():
    assert len(ALLOWED_COMMANDS) == 10
    names = [cmd.name for cmd in ALLOWED_COMMANDS]
    assert "read_environment_description" in names
    assert "read_status" in names
    assert "read_application_logs" in names
    assert "read_system_metrics" in names
    assert "read_network_stats" in names
    assert "audit_telemetry_pipeline" in names
    assert "acknowledge_healthy" in names
    assert "bypass_synthetic_telemetry" in names
    assert "restart_upstream_service" in names
    assert "finalize" in names


def test_1984_command_categories():
    categories = {cmd.category for cmd in ALLOWED_COMMANDS}
    assert CommandCategory.read in categories
    assert CommandCategory.inspect in categories
    assert CommandCategory.act in categories


def test_1984_allowed_command_immutability():
    cmd = ALLOWED_COMMANDS[0]
    assert isinstance(cmd, AllowedCommand)
    with pytest.raises(FrozenInstanceError):
        cmd.name = "new_name"  # type: ignore[misc]


def test_1984_describe_allowed_commands():
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


def test_1984_validate_command_name():
    validate_command_name("bypass_synthetic_telemetry")
    validate_command_name("restart_upstream_service")

    with pytest.raises(CommandError, match="Unknown command: 'fake_command'"):
        validate_command_name("fake_command")


def test_1984_command_indices_match():
    assert describe_environment_description_command_index() == 0
    for cmd in ALLOWED_COMMANDS:
        assert cmd.name in COMMAND_LABEL_TO_INDEX
