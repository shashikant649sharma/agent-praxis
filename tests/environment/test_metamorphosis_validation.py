"""Tests for Metamorphosis validation suite and CLI verification."""

from agent_praxis.commands.validate import main, validate_metamorphosis


def test_metamorphosis_validation_pipeline():
    results = validate_metamorphosis()
    assert results["reset_deterministic"] is True
    assert results["description_valid"]["valid"] is True
    assert results["known_good_passes"] is True
    assert results["known_bad_fails"] is True


def test_metamorphosis_validate_cli_main():
    code = main(["metamorphosis"])
    assert code == 0
