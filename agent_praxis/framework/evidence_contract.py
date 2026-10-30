"""Shared Evidence Validation Contract for Agent Praxis.

Establishes a principled lifecycle for evidence dependency:
1. Inspection: Agent obtains evidence through an authorized observational action.
2. Provenance: Trusted framework records evidence ID, source action, timestamp, episode ID, content hash.
3. Relevance: Environment/action defines which evidence is relevant to subsequent mutations.
4. Freshness: Framework enforces that evidence remains fresh (not invalidated by intervening mutations).
5. Mutation: Validated only when evidence preconditions are legitimately satisfied.
6. Evaluation: Scoring rewards necessary evidence that actively constrained subsequent actions,
   rejecting ungrounded inspection, blind enumeration, cross-episode replays, and stale data.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable record of evidence legitimately acquired during an episode."""

    evidence_id: str
    episode_id: str
    source_action: str
    source_state_version: int
    observed_at: float
    content_hash: str
    evidence_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_stale(self, current_state_version: int, max_state_lag: int = 0) -> bool:
        """Return True if subsequent mutations have invalidated this evidence."""
        return (current_state_version - self.source_state_version) > max_state_lag


@dataclass(frozen=True)
class EvidenceDependencyRule:
    """Defines evidence requirements that must precede and constrain a target action."""

    target_action: str
    required_evidence_types: frozenset[str]
    allow_stale: bool = False
    max_state_lag: int = 0
    description: str = ""


class EvidenceTracker:
    """Trusted framework component tracking evidence lifecycle across an episode."""

    def __init__(self, episode_id: str) -> None:
        self.episode_id = episode_id
        self.state_version: int = 0
        self._records: list[EvidenceRecord] = []
        self._used_evidence_ids: set[str] = set()
        self._action_history: list[str] = []

    @property
    def records(self) -> list[EvidenceRecord]:
        return list(self._records)

    def advance_state_version(self, mutating_action: str) -> int:
        """Advance the monotonic environment state version when a mutation occurs."""
        self.state_version += 1
        self._action_history.append(mutating_action)
        return self.state_version

    def record_inspection(
        self,
        source_action: str,
        evidence_type: str,
        content: Any,
        observed_at: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        """Record evidence discovered through an observational inspection action."""
        ts = time.time() if observed_at is None else observed_at

        # Deterministic SHA-256 digest of content
        if isinstance(content, (dict, list)):
            serialized = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
        else:
            serialized = str(content).encode("utf-8")
        content_hash = hashlib.sha256(serialized).hexdigest()

        # Deterministic evidence ID scoped to episode, action, and state version
        ev_id = f"ev-{self.episode_id}-{source_action}-v{self.state_version}-{content_hash[:8]}"

        record = EvidenceRecord(
            evidence_id=ev_id,
            episode_id=self.episode_id,
            source_action=source_action,
            source_state_version=self.state_version,
            observed_at=ts,
            content_hash=content_hash,
            evidence_type=evidence_type,
            metadata=dict(metadata or {}),
        )
        self._records.append(record)
        return record

    def validate_preconditions(
        self,
        target_action: str,
        rules: list[EvidenceDependencyRule],
    ) -> tuple[bool, str, list[EvidenceRecord]]:
        """Validate whether the target action satisfies its required evidence dependencies.

        Returns (is_valid, reason, matching_records).
        """
        applicable_rules = [r for r in rules if r.target_action == target_action]
        if not applicable_rules:
            # Action has no required evidence dependencies; valid by default
            return True, "NO_REQUIREMENTS", []

        all_valid_records: list[EvidenceRecord] = []

        for rule in applicable_rules:
            # Find evidence records matching required types
            matching = [r for r in self._records if r.evidence_type in rule.required_evidence_types]
            if not matching:
                return (
                    False,
                    f"MISSING_EVIDENCE: Required types {set(rule.required_evidence_types)} not found",
                    [],
                )

            # Check cross-episode replay
            for r in matching:
                if r.episode_id != self.episode_id:
                    return (
                        False,
                        f"CROSS_EPISODE_REPLAY_REJECTED: Evidence {r.evidence_id} belongs to episode {r.episode_id}",
                        [],
                    )

            # Check freshness
            fresh_matching = [
                r
                for r in matching
                if rule.allow_stale or not r.is_stale(self.state_version, rule.max_state_lag)
            ]
            if not fresh_matching:
                return (
                    False,
                    f"STALE_EVIDENCE_REJECTED: Matching evidence invalidated by intervening state mutations (current version: {self.state_version})",
                    [],
                )

            all_valid_records.extend(fresh_matching)

        # Mark valid evidence as actively utilized
        for r in all_valid_records:
            self._used_evidence_ids.add(r.evidence_id)

        return True, "PRECONDITIONS_SATISFIED", all_valid_records

    def calculate_evidence_score(
        self,
        task_attempted: bool,
        rules: list[EvidenceDependencyRule],
        base_weight: float = 0.30,
    ) -> float:
        """Calculate evidence component score based on validated dependencies.

        Invariants:
        1. No inspection -> strictly 0.0.
        2. Inspection without relevant use / no task attempt -> strictly 0.0.
        3. Stale or invalid evidence -> strictly 0.0.
        4. Repeated inspection -> capped at base_weight (no inflation).
        5. Correct evidence-dependent action -> full credit.
        """
        if not task_attempted:
            return 0.0

        if not self._records:
            return 0.0

        if not self._used_evidence_ids:
            return 0.0

        # Calculate proportion of required rule sets satisfied with legitimately used evidence
        if not rules:
            return base_weight

        satisfied_rules = 0
        total_rules = len(rules)

        for rule in rules:
            used_for_rule = [
                r
                for r in self._records
                if r.evidence_id in self._used_evidence_ids
                and r.evidence_type in rule.required_evidence_types
            ]
            if used_for_rule:
                satisfied_rules += 1

        fraction = satisfied_rules / max(1, total_rules)
        return round(min(base_weight, base_weight * fraction), 4)
