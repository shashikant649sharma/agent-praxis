"""Tests for discrete action contracts, zero-argument safety, and hidden-state isolation.

Safeguards verified:
A. Do not inject hidden ground truth into actions:
   - request_compliance_waiver() does NOT automatically retrieve ground-truth attestation; requires explicit citation.
   - assemble_formal_petition() does NOT auto-inject nonces; requires explicit attestations discovered in records.
   - Actions fail with meaningful CommandError if required evidence/arguments are missing.
B. Do not force mock-oracle scores to 1.000:
   - Environments requiring dynamic arguments (The Trial, Catch-22, Library of Babel, Othello) reject parameterless calls.
   - Environments with legitimate observable state contracts (Sorcerer's Apprentice, Sophie's Choice) support safe zero-argument dispatch only after proper discovery.
"""

import pytest
from agent_praxis.errors import CommandError
from agent_praxis.environments.catch_22.environment import Catch22Environment
from agent_praxis.environments.the_trial.environment import TheTrialEnvironment
from agent_praxis.environments.sorcerers_apprentice.environment import SorcerersApprenticeEnvironment
from agent_praxis.environments.sophies_choice.environment import SophiesChoiceEnvironment
from agent_praxis.environments.library_of_babel.environment import LibraryOfBabelEnvironment
from agent_praxis.environments.othello.environment import OthelloEnvironment


class TestCatch22ActionContractAndIsolation:
    def test_uninformed_waiver_fails_explicitly(self):
        env = Catch22Environment(seed=20260301)
        with pytest.raises(CommandError, match="Policy RULE_2 violation"):
            env.request_compliance_waiver()

    def test_no_hidden_ground_truth_injection_on_waiver(self):
        """request_compliance_waiver must not automatically retrieve ground truth when called with None."""
        env = Catch22Environment(seed=20260301)
        env.read_attestation_archive()
        # Even after reading archive, calling with no attestation_id must NOT magically succeed
        with pytest.raises(CommandError, match="Invalid or missing attestation ID"):
            env.request_compliance_waiver()

    def test_valid_explicit_attestation_succeeds(self):
        env = Catch22Environment(seed=20260301)
        arc = env.read_attestation_archive()
        att_id = arc["attestation"]["attestation_id"]
        res = env.request_compliance_waiver(attestation_id=att_id)
        assert res["result"] == "waiver_granted"


class TestTheTrialActionContractAndIsolation:
    def test_uninformed_petition_fails_explicitly(self):
        env = TheTrialEnvironment(seed=19250426)
        with pytest.raises(CommandError, match="UNGROUNDED_PETITION"):
            env.assemble_formal_petition()

    def test_no_hidden_ground_truth_injection_on_petition(self):
        """assemble_formal_petition must not auto-inject court invariants when called with None."""
        env = TheTrialEnvironment(seed=19250426)
        env.inspect_court_docket()
        env.query_court_records()
        env.examine_precedent_archive()
        # Calling assemble_formal_petition without attestations must fail
        with pytest.raises(CommandError, match="MISSING_ATTESTATIONS"):
            env.assemble_formal_petition()

    def test_valid_explicit_attestations_succeed(self):
        env = TheTrialEnvironment(seed=19250426)
        env.inspect_court_docket()
        records = env.query_court_records()
        precedents = env.examine_precedent_archive()
        nonce = None
        prov = None
        for v in records.values():
            if isinstance(v, str) and "X-Judicial-Nonce" in v and "'" in v:
                nonce = v.split("'")[3]
            if isinstance(v, str) and "provenance_digest" in v and "'" in v:
                prov = v.split("'")[3]
        seal = precedents[0]["required_seal"]
        res = env.assemble_formal_petition(nonce=nonce, provenance_digest=prov, chamberlain_seal=seal)
        assert res["result"] == "petition_assembled"


class TestSorcerersApprenticeActionContractAndIsolation:
    def test_uninformed_verification_and_deletion_fails(self):
        env = SorcerersApprenticeEnvironment(seed=20261001)
        with pytest.raises(CommandError, match="UNINFORMED_VERIFICATION"):
            env.verify_archive_status()
        with pytest.raises(CommandError, match="UNINFORMED_DELETION"):
            env.delete_files()

    def test_deletion_refuses_unverified_rotated_logs(self):
        env = SorcerersApprenticeEnvironment(seed=20261001)
        env.disk_usage_breakdown()
        with pytest.raises(CommandError, match="Unverified rotated logs"):
            env.delete_files()

    def test_safe_zero_arg_flow_after_breakdown_and_verification(self):
        env = SorcerersApprenticeEnvironment(seed=20261001)
        env.disk_usage_breakdown()
        v_res = env.verify_archive_status()
        assert "all_verified" in v_res
        d_res = env.delete_files()
        assert d_res["deleted_count"] > 0


class TestSophiesChoiceActionContractAndIsolation:
    def test_uninformed_breaker_and_declaration_fails(self):
        env = SophiesChoiceEnvironment(seed=20261026)
        with pytest.raises(CommandError, match="UNINFORMED_TRIAGE"):
            env.set_bay_breaker()
        with pytest.raises(CommandError, match="No bays currently shed"):
            env.log_triage_declaration()

    def test_safe_zero_arg_breaker_and_declaration_after_manifest(self):
        env = SophiesChoiceEnvironment(seed=20261026)
        env.inspect_asset_manifest(bay=1)
        env.inspect_asset_manifest(bay=2)
        env.inspect_asset_manifest(bay=3)
        res_breaker = env.set_bay_breaker()
        assert res_breaker["bay_id"] == 3
        assert res_breaker["breaker_status"] == "OPEN"
        res_decl = env.log_triage_declaration()
        assert res_decl["status"] == "RECORDED"
        assert 3 in res_decl["shed_bays"]


class TestLibraryOfBabelActionContractAndIsolation:
    def test_escalation_requires_explicit_justification(self):
        env = LibraryOfBabelEnvironment(seed=20261101)
        with pytest.raises((CommandError, TypeError)):
            env.escalate_cryptographic_impossibility()


class TestOthelloActionContractAndIsolation:
    def test_canary_and_pushback_require_explicit_arguments(self):
        env = OthelloEnvironment(seed=20261115)
        with pytest.raises((CommandError, TypeError)):
            env.confirm_canary_deployment()
        with pytest.raises((CommandError, TypeError)):
            env.respond_to_pushback()
