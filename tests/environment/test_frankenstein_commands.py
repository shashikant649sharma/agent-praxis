"""Command allowlist and validation tests for Frankenstein environment."""

import pytest

from agent_praxis.environments.frankenstein import commands as cmd_mod


def test_frankenstein_allowed_commands_structure():
    assert len(cmd_mod.ALLOWED_COMMANDS) == 10
    names = [c.name for c in cmd_mod.ALLOWED_COMMANDS]
    assert "read_environment_description" in names
    assert "read_pipeline_status" in names
    assert "read_pipeline_logs" in names
    assert "read_throughput_metrics" in names
    assert "read_enrichment_cache_stats" in names
    assert "audit_sink_idempotency" in names
    assert "run_interaction_diagnostic" in names
    assert "apply_ttl_realignment_fix" in names
    assert "force_restart_pipeline" in names
    assert "finalize" in names


def test_frankenstein_command_indices():
    for _name, idx in cmd_mod.COMMAND_LABEL_TO_INDEX.items():
        assert 0 <= idx < 10


def test_frankenstein_validate_command_name():
    cmd_mod.validate_command_name("read_pipeline_status")
    cmd_mod.validate_command_name("apply_ttl_realignment_fix")

    with pytest.raises(cmd_mod.CommandError, match="Unknown command"):
        cmd_mod.validate_command_name("rm -rf /")


def test_describe_allowed_commands():
    desc = cmd_mod.describe_allowed_commands()
    assert len(desc) == 10
    for item in desc:
        assert "name" in item
        assert "category" in item
        assert "description" in item
