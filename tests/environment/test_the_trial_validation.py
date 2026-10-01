"""Tests for The Trial validation suite and CLI verification."""

from agent_praxis.commands.validate import main, validate_the_trial


def test_the_trial_validation_pipeline():
    results = validate_the_trial()
    assert results["reset_deterministic"] is True
    assert results["description_valid"]["valid"] is True
    assert results["known_good_passes"] is True
    assert results["known_bad_fails"] is True


def test_the_trial_validate_cli_main():
    code = main(["the-trial"])
    assert code == 0
