"""Tests for 1984 validation suite and CLI verification."""

from agent_praxis.commands.validate import main, validate_1984


def test_1984_validation_pipeline():
    results = validate_1984()
    assert results["reset_deterministic"] is True
    assert results["description_valid"]["valid"] is True
    assert results["known_good_passes"] is True
    assert results["known_bad_fails"] is True


def test_1984_validate_cli_main():
    code = main(["1984"])
    assert code == 0
