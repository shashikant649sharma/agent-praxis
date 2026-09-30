"""Tests for command validation in the Dorian Gray environment."""

import agent_praxis.environments.dorian_gray.commands as cmd_mod


def test_unknown_command_raises_command_error():
    """Calling an unknown command name via validate_command_name raises CommandError."""
    try:
        cmd_mod.validate_command_name("nonexistent_command_xyz")
    except cmd_mod.CommandError:
        pass  # expected
    else:
        raise AssertionError("Expected CommandError for unknown command")


def test_known_command_does_not_raise():
    """Known command names do NOT raise CommandError."""
    # Test a few known commands
    for name in ("read_status", "read_logs", "attempt_worker_recovery", "finalize"):
        cmd_mod.validate_command_name(name)  # should not raise


def test_describe_allowed_commands_returns_non_empty_list():
    """describe_allowed_commands() returns a non-empty list of dicts with required keys."""
    result = cmd_mod.describe_allowed_commands()

    assert isinstance(result, list), "describe_allowed_commands must return a list"
    assert len(result) > 0, "describe_allowed_commands must return non-empty list"

    for entry in result:
        assert isinstance(entry, dict), "Each entry must be a dict"
        assert "category" in entry, "Entry missing 'category' key"
        assert "name" in entry, "Entry missing 'name' key"
        assert "description" in entry, "Entry missing 'description' key"
