"""Validation harness test for Frankenstein environment."""

from agent_praxis.commands.validate import validate_frankenstein


def test_frankenstein_validation_harness():
    res = validate_frankenstein()
    assert res["reset_deterministic"] is True
    assert res["description_valid"]["valid"] is True
    assert res["known_good_passes"] is True
    assert res["known_bad_fails"] is True
