"""Tests for trajectory determinism in the Dorian Gray environment.

Same seed + same ordered action sequence = identical final state and evaluator
score across repeated runs. This is DIFFERENT from test_state_determinism.py
(which tests initial_state freeze() determinism — this must call actual
environment methods in sequence).
"""

import contextlib

from agent_praxis.environments.dorian_gray.commands import CommandError
from agent_praxis.environments.dorian_gray.environment import DorianGrayEnvironment
from agent_praxis.environments.dorian_gray.state import are_equal
from agent_praxis.framework.evaluation import schema


def _known_good_trajectory(env):
    """The canonical known-good action sequence."""
    env.read_status()
    env.read_logs()
    env.read_metrics()
    env.read_retention_index_summary()
    env.read_reconciliation_report()
    env.run_retention_audit_diagnostic()
    env.attempt_worker_recovery()
    env.finalize()


def _make_snapshot_and_score(env):
    snap = env.snapshot_for_evaluation()
    result = schema.make_run_result(
        snap, environment_name="dorian-gray", command_log=snap.get("command_log", [])
    )
    return snap, result


class TestTrajectoryDeterminism:
    """Same seed + same action sequence = identical outcome across runs."""

    def test_known_good_same_snapshot(self):
        seed = 20260201
        env1 = DorianGrayEnvironment(seed=seed)
        _known_good_trajectory(env1)
        snap1, result1 = _make_snapshot_and_score(env1)

        env2 = DorianGrayEnvironment(seed=seed)
        _known_good_trajectory(env2)
        snap2, result2 = _make_snapshot_and_score(env2)

        assert are_equal(env1._state, env2._state)
        assert snap1 == snap2
        assert result1.score == result2.score
        assert result1.task_success == result2.task_success

    def test_known_good_same_command_log(self):
        seed = 20260201
        env1 = DorianGrayEnvironment(seed=seed)
        _known_good_trajectory(env1)
        snap1 = env1.snapshot_for_evaluation()

        env2 = DorianGrayEnvironment(seed=seed)
        _known_good_trajectory(env2)
        snap2 = env2.snapshot_for_evaluation()

        assert snap1["command_log"] == snap2["command_log"]

    def test_different_seeds_different_outcomes(self):
        env_a = DorianGrayEnvironment(seed=20260201)
        _known_good_trajectory(env_a)
        env_b = DorianGrayEnvironment(seed=99999999)
        _known_good_trajectory(env_b)
        assert not are_equal(env_a._state, env_b._state)

    def test_superficial_trajectory_deterministic(self):
        seed = 20260201

        def superficial(env):
            env.read_status()
            env.patch_health_report()
            env.finalize()

        env1 = DorianGrayEnvironment(seed=seed)
        superficial(env1)
        snap1, result1 = _make_snapshot_and_score(env1)

        env2 = DorianGrayEnvironment(seed=seed)
        superficial(env2)
        snap2, result2 = _make_snapshot_and_score(env2)

        assert snap1["command_log"] == snap2["command_log"]
        assert result1.score == result2.score == 0.0

    def test_uninformed_recovery_trajectory_deterministic(self):
        """attempt_worker_recovery() without prior evidence-gathering raises
        CommandError (M4 anti-pattern). After catching it and finalizing,
        score is 0.0 — and the trajectory is still deterministic.
        """
        seed = 20260201

        def uninformed(env):
            with contextlib.suppress(CommandError):
                env.attempt_worker_recovery()
            env.finalize()

        env1 = DorianGrayEnvironment(seed=seed)
        uninformed(env1)
        snap1, result1 = _make_snapshot_and_score(env1)

        env2 = DorianGrayEnvironment(seed=seed)
        uninformed(env2)
        snap2, result2 = _make_snapshot_and_score(env2)

        assert snap1["command_log"] == snap2["command_log"]
        assert result1.score == result2.score == 0.0
