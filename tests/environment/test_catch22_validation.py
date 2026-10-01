"""Tests for Catch-22 validation suite and CLI verification."""

from agent_praxis.commands.validate import main, validate_catch_22


def test_catch22_validation_pipeline():
    results = validate_catch_22()
    assert results["reset_deterministic"] is True
    assert results["description_valid"]["valid"] is True
    assert results["known_good_passes"] is True
    assert results["known_bad_fails"] is True


def test_catch22_validate_cli_main():
    code = main(["catch-22"])
    assert code == 0
