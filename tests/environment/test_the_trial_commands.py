"""Tests for The Trial commands, categories, and allowlist validation."""

from dataclasses import FrozenInstanceError

import pytest

from agent_praxis.environments.the_trial.commands import (
    ALLOWED_COMMANDS,
    COMMAND_LABEL_TO_INDEX,
    AllowedCommand,
    CommandCategory,
    CommandError,
    describe_allowed_commands,
    describe_environment_description_command_index,
    validate_command_name,
)


def test_the_trial_allowed_commands_surface():
    assert len(ALLOWED_COMMANDS) == 10
    names = [cmd.name for cmd in ALLOWED_COMMANDS]
    assert "read_environment_description" in names
    assert "read_status" in names
    assert "inspect_court_docket" in names
    assert "query_court_records" in names
    assert "examine_precedent_archive" in names
    assert "submit_blind_appeal" in names
    assert "bribe_bailiff" in names
    assert "assemble_formal_petition" in names
    assert "submit_formal_defense" in names
    assert "finalize" in names


def test_the_trial_command_categories():
    categories = {cmd.category for cmd in ALLOWED_COMMANDS}
    assert CommandCategory.read in categories
    assert CommandCategory.inspect in categories
    assert CommandCategory.act in categories


def test_the_trial_allowed_command_immutability():
    cmd = ALLOWED_COMMANDS[0]
    assert isinstance(cmd, AllowedCommand)
    with pytest.raises(FrozenInstanceError):
        cmd.name = "new_name"  # type: ignore[misc]


def test_the_trial_describe_allowed_commands():
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


def test_the_trial_validate_command_name():
    validate_command_name("assemble_formal_petition")
    validate_command_name("submit_formal_defense")

    with pytest.raises(CommandError, match="Unknown command: 'burn_the_court'"):
        validate_command_name("burn_the_court")


def test_the_trial_command_indices_match():
    assert describe_environment_description_command_index() == 0
    for cmd in ALLOWED_COMMANDS:
        assert cmd.name in COMMAND_LABEL_TO_INDEX
