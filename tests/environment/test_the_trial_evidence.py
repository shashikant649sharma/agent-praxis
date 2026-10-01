"""Tests for The Trial evidence presentation layer and formatting."""

from agent_praxis.environments.the_trial.evidence import (
    AllowedActionsList,
    court_docket,
    court_records,
    precedent_archive,
    public_description,
)
from agent_praxis.environments.the_trial.state import initial_state
from agent_praxis.framework.evaluation.validation import assert_environment_description


def test_the_trial_public_description_validation():
    state = initial_state(seed=19250426)
    desc = public_description(state)
    val_result = assert_environment_description(desc)
    assert val_result["valid"] is True, f"Description validation failed: {val_result['checks']}"
    assert desc["identity"]["name"] == "the-trial"
    assert "Gatekeeper" in desc["identity"]["concept"]


def test_the_trial_allowed_actions_list_membership():
    actions = AllowedActionsList([{"name": "assemble_formal_petition"}, {"name": "submit_formal_defense"}])
    assert "assemble_formal_petition" in actions
    assert "submit_formal_defense" in actions
    assert "unknown_command" not in actions


def test_the_trial_court_docket_content():
    state = initial_state(seed=19250426)
    docket = court_docket(state)
    assert docket["case_number"] == "K-1925-PRX"
    assert "Josef K." in docket["accused"]
    assert docket["gatekeeper_code"] == "ERR_OPAQ_418"


def test_the_trial_court_records_content():
    state = initial_state(seed=19250426)
    records = court_records(state)
    assert "procedural_article_9" in records
    assert "CH-9941-NONCE" in records["procedural_article_9"]
    assert "procedural_article_14" in records
    assert "e3b0c442" in records["procedural_article_14"]


def test_the_trial_precedent_archive_content():
    state = initial_state(seed=19250426)
    archive = precedent_archive(state)
    assert len(archive) >= 2
    titorelli = next(p for p in archive if p["precedent_case"] == "CASE-1899-TITORELLI")
    assert titorelli["outcome"] == "OSTENSIBLE_ACQUITTAL"
    assert titorelli["required_seal"] == "SEAL_OF_THE_CHAMBERLAIN_V1"
