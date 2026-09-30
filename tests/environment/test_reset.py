"""Tests for environment reset behavior in the Dorian Gray environment."""

import agent_praxis.environments.dorian_gray.environment as env_mod


def test_reset_produces_same_fingerprint_as_fresh():
    """After reset(seed=20260201), initial_state_fingerprint() matches a fresh environment."""
    fresh = env_mod.DorianGrayEnvironment(seed=20260201)
    fresh_fp = fresh.initial_state_fingerprint()

    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.reset(seed=20260201)
    reset_fp = env.initial_state_fingerprint()

    assert fresh_fp == reset_fp, "Reset fingerprint must match fresh environment fingerprint"


def test_reset_read_status_matches_fresh():
    """After reset(seed=20260201), read_status() returns the same values as a fresh environment."""
    fresh = env_mod.DorianGrayEnvironment(seed=20260201)
    fresh_status = fresh.read_status()

    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.reset(seed=20260201)
    reset_status = env.read_status()

    assert fresh_status == reset_status, (
        "Reset read_status must match fresh environment read_status"
    )


def test_reset_clears_command_log():
    """After reset, the command log is cleared (fresh state has empty command_log).

    snapshot_for_evaluation() requires finalize(), and finalize() records its
    own command (index 9). So we compare: a fresh finalized env's log vs a
    reset-then-finalized env's log — both should be identical (just [9]).
    """
    # Fresh env: finalize and check log
    fresh = env_mod.DorianGrayEnvironment(seed=20260201)
    fresh.finalize()
    fresh_log = fresh.snapshot_for_evaluation()["command_log"]

    # Env with prior commands, then reset
    env = env_mod.DorianGrayEnvironment(seed=20260201)
    env.read_status()
    env.read_logs()
    env.reset(seed=20260201)
    env.finalize()
    reset_log = env.snapshot_for_evaluation()["command_log"]

    # Reset should have cleared the prior commands; only finalize remains
    assert reset_log == fresh_log, "Reset should clear command log to fresh baseline"
    # The prior commands (read_status=1, read_logs=2) should not be in the log
    assert 1 not in reset_log, "read_status command should be cleared by reset"
    assert 2 not in reset_log, "read_logs command should be cleared by reset"
