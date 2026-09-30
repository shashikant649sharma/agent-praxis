"""Tests for state determinism in the Dorian Gray environment."""

import agent_praxis.environments.dorian_gray.state as state_mod


def test_initial_state_same_seed_same_freeze():
    """initial_state(seed=20260201) called twice produces identical freeze() output."""
    s1 = state_mod.initial_state(seed=20260201)
    s2 = state_mod.initial_state(seed=20260201)
    assert s1.freeze() == s2.freeze(), "Same seed must produce identical freeze output"


def test_initial_state_different_seeds_different_freeze():
    """initial_state with seed=20260201 and seed=99999999 produce different freeze output."""
    s1 = state_mod.initial_state(seed=20260201)
    s2 = state_mod.initial_state(seed=99999999)
    assert s1.freeze() != s2.freeze(), (
        "Different seeds must produce different freeze output"
    )


def test_reset_to_initial_matches_initial_state():
    """reset_to_initial(seed=20260201) produces the same state as initial_state(seed=20260201)."""
    s1 = state_mod.initial_state(seed=20260201)
    s2 = state_mod.reset_to_initial(seed=20260201)
    assert s1.freeze() == s2.freeze(), "reset_to_initial must match initial_state for the same seed"
