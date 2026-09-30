"""Tests for lifecycle edge cases in the Dorian Gray environment."""

import pytest

from agent_praxis.environments.dorian_gray.commands import CommandError
from agent_praxis.environments.dorian_gray.environment import DorianGrayEnvironment


class TestLifecycleEdgeCases:
    """Well-defined behavior at lifecycle boundaries."""

    def test_finalize_twice_raises(self):
        env = DorianGrayEnvironment(seed=20260201)
        env.finalize()
        with pytest.raises(CommandError, match="finalized"):
            env.finalize()

    def test_actions_after_finalize_raise(self):
        env = DorianGrayEnvironment(seed=20260201)
        env.finalize()
        actions = [
            "description", "read_status", "read_logs", "read_metrics",
            "read_retention_index_summary", "read_reconciliation_report",
            "run_retention_audit_diagnostic", "attempt_worker_recovery",
            "patch_health_report",
        ]
        for name in actions:
            with pytest.raises(CommandError, match="finalized"):
                getattr(env, name)()

    def test_reset_clears_command_log(self):
        env = DorianGrayEnvironment(seed=20260201)
        env.read_status()
        env.read_logs()
        env.reset(seed=20260201)
        snap = env.snapshot_for_evaluation()
        assert snap["command_log"] == []

    def test_reset_clears_finalized_flag(self):
        env = DorianGrayEnvironment(seed=20260201)
        env.finalize()
        env.reset(seed=20260201)
        result = env.read_status()
        assert result["service_status"] == "healthy"

    def test_reset_different_seed_changes_state(self):
        env = DorianGrayEnvironment(seed=20260201)
        fp1 = env.initial_state_fingerprint()
        env.reset(seed=99999999)
        fp2 = env.initial_state_fingerprint()
        assert fp1 != fp2

    def test_invalid_action_name_raises(self):
        env = DorianGrayEnvironment(seed=20260201)
        with pytest.raises(AttributeError):
            env.nonexistent_action()

    def test_snapshot_before_finalize_empty_mutations(self):
        env = DorianGrayEnvironment(seed=20260201)
        env.read_status()
        snap = env.snapshot_for_evaluation()
        assert snap["mutable_state"] == {}

    def test_snapshot_after_finalize_has_mutations(self):
        env = DorianGrayEnvironment(seed=20260201)
        env.read_status()
        env.patch_health_report()
        env.finalize()
        snap = env.snapshot_for_evaluation()
        assert snap["mutable_state"].get("health_report_patched") is True
