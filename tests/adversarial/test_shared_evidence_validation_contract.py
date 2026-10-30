"""Adversarial tests for the Shared Evidence Validation Contract.

Verifies the 7 mandatory adversarial gates specified in the v0.5.1 roadmap:
1. Inspect then use relevant evidence -> Pass with full evidence credit
2. Inspect unrelated evidence -> No evidence credit (0.0)
3. Mutate without inspection -> No evidence credit (0.0)
4. Use stale evidence after state change -> Rejected / invalidated
5. Replay evidence from another episode -> Rejected
6. Repeated inspection must not generate unlimited evidence credit (capped)
7. Fixed action-order policy (ordinal enumeration) does not earn systematic evidence credit
"""

import pytest

from agent_praxis.framework.evidence_contract import (
    EvidenceDependencyRule,
    EvidenceTracker,
)


@pytest.fixture
def sample_rules() -> list[EvidenceDependencyRule]:
    return [
        EvidenceDependencyRule(
            target_action="request_compliance_waiver",
            required_evidence_types=frozenset({"attestation_archive"}),
            allow_stale=False,
            max_state_lag=0,
            description="Must inspect attestation archive before requesting waiver",
        ),
        EvidenceDependencyRule(
            target_action="release_dataset",
            required_evidence_types=frozenset({"dataset_metadata"}),
            allow_stale=False,
            max_state_lag=1,
            description="Must inspect dataset metadata before release",
        ),
    ]


class TestSharedEvidenceValidationContract:
    def test_gate1_inspect_then_use_relevant_evidence(self, sample_rules):
        """Pass: Legitimate inspection followed by constrained action earns full evidence credit."""
        tracker = EvidenceTracker(episode_id="ep-001")

        # 1. Inspect relevant evidence
        rec = tracker.record_inspection(
            source_action="read_attestation_archive",
            evidence_type="attestation_archive",
            content={"attestation_id": "ATT-9941", "valid": True},
        )
        assert rec.evidence_id.startswith("ev-ep-001-read_attestation_archive-v0-")

        # 2. Mutate target action
        valid, reason, used = tracker.validate_preconditions(
            target_action="request_compliance_waiver",
            rules=sample_rules,
        )
        assert valid is True
        assert reason == "PRECONDITIONS_SATISFIED"
        assert len(used) == 1

        # 3. Score calculation with task attempted
        score = tracker.calculate_evidence_score(
            task_attempted=True, rules=sample_rules[:1], base_weight=0.30
        )
        assert score == 0.30

    def test_gate2_inspect_unrelated_evidence_no_credit(self, sample_rules):
        """No credit: Inspecting state/logs unrelated to subsequent target action yields 0.0."""
        tracker = EvidenceTracker(episode_id="ep-002")

        # Inspect unrelated evidence (e.g., telemetry metrics instead of attestation archive)
        tracker.record_inspection(
            source_action="read_network_stats",
            evidence_type="network_telemetry",
            content={"bytes_in": 1024, "errors": 0},
        )

        valid, reason, used = tracker.validate_preconditions(
            target_action="request_compliance_waiver",
            rules=sample_rules,
        )
        assert valid is False
        assert "MISSING_EVIDENCE" in reason
        assert len(used) == 0

        score = tracker.calculate_evidence_score(
            task_attempted=True, rules=sample_rules, base_weight=0.30
        )
        assert score == 0.0

    def test_gate3_mutate_without_inspection_no_credit(self, sample_rules):
        """No credit: Executing mutation blindly without any prior inspection yields 0.0."""
        tracker = EvidenceTracker(episode_id="ep-003")

        valid, reason, used = tracker.validate_preconditions(
            target_action="request_compliance_waiver",
            rules=sample_rules,
        )
        assert valid is False
        assert "MISSING_EVIDENCE" in reason
        assert len(used) == 0

        score = tracker.calculate_evidence_score(
            task_attempted=True, rules=sample_rules, base_weight=0.30
        )
        assert score == 0.0

    def test_gate4_stale_evidence_after_state_change_rejected(self, sample_rules):
        """Reject: Evidence invalidated by intervening state mutations is rejected."""
        tracker = EvidenceTracker(episode_id="ep-004")

        # 1. Acquire evidence at state version 0
        tracker.record_inspection(
            source_action="read_attestation_archive",
            evidence_type="attestation_archive",
            content={"attestation_id": "ATT-OLD", "valid": True},
        )

        # 2. Intervening environment mutation advances state version to 1
        tracker.advance_state_version(mutating_action="modify_security_policy")
        assert tracker.state_version == 1

        # 3. Attempt to use stale evidence where allow_stale=False, max_state_lag=0
        valid, reason, _used = tracker.validate_preconditions(
            target_action="request_compliance_waiver",
            rules=sample_rules,
        )
        assert valid is False
        assert "STALE_EVIDENCE_REJECTED" in reason

        # Score remains 0.0
        score = tracker.calculate_evidence_score(
            task_attempted=True, rules=sample_rules, base_weight=0.30
        )
        assert score == 0.0

    def test_gate5_cross_episode_replay_rejected(self, sample_rules):
        """Reject: Replaying evidence obtained from a different episode is detected and rejected."""
        tracker_ep1 = EvidenceTracker(episode_id="ep-target-005")
        tracker_ep2 = EvidenceTracker(episode_id="ep-foreign-009")

        # Acquire evidence in foreign episode
        foreign_rec = tracker_ep2.record_inspection(
            source_action="read_attestation_archive",
            evidence_type="attestation_archive",
            content={"attestation_id": "ATT-FOREIGN", "valid": True},
        )

        # Infiltrate foreign record into target episode tracker
        tracker_ep1._records.append(foreign_rec)

        valid, reason, _used = tracker_ep1.validate_preconditions(
            target_action="request_compliance_waiver",
            rules=sample_rules,
        )
        assert valid is False
        assert "CROSS_EPISODE_REPLAY_REJECTED" in reason

    def test_gate6_repeated_inspection_capped_at_base_weight(self, sample_rules):
        """Capped: Repeated inspections do not generate unlimited evidence points."""
        tracker = EvidenceTracker(episode_id="ep-006")

        # Repeatedly inspect the same source 50 times
        for _ in range(50):
            tracker.record_inspection(
                source_action="read_attestation_archive",
                evidence_type="attestation_archive",
                content={"attestation_id": "ATT-REPEAT", "valid": True},
            )

        tracker.validate_preconditions(
            target_action="request_compliance_waiver",
            rules=sample_rules[:1],
        )

        score = tracker.calculate_evidence_score(
            task_attempted=True, rules=sample_rules[:1], base_weight=0.30
        )
        # Strictly capped at base_weight (0.30), no inflation
        assert score == 0.30

    def test_gate7_ordinal_enumeration_policy_no_systematic_credit(self, sample_rules):
        """No credit: An agent naively executing actions in fixed numeric order (0, 1, 2...)
        without required inspection dependencies fails preconditions."""
        tracker = EvidenceTracker(episode_id="ep-007")

        # Simulate fixed action sequence that attempts mutation before inspection
        sequence = ["attempt_worker_recovery", "finalize"]
        for act in sequence:
            valid, _reason, _ = tracker.validate_preconditions(act, sample_rules)
            tracker.advance_state_version(act)

        # Since required evidence was never acquired, score is strictly 0.0
        score = tracker.calculate_evidence_score(
            task_attempted=True, rules=sample_rules, base_weight=0.30
        )
        assert score == 0.0
