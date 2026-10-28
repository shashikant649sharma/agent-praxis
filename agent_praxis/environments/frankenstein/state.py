"""Deterministic state model for the Frankenstein environment (v0.3).

The state model represents a multi-service pipeline (Ingress -> Enrichment -> Sink)
where every individual service passes its own health checks, but their composition
produces silent event loss due to a subtle interaction between cache TTL and timestamp
normalization.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from agent_praxis.framework.variants import EnvironmentVariant, get_variant_config

SEED = 18180101

START_AT = datetime(2026, 10, 12, 10, 0, 0, tzinfo=UTC)


class ServiceHealth(StrEnum):
    healthy = "HEALTHY"
    degraded = "DEGRADED"
    restarted = "RESTARTED"


@dataclass(frozen=True)
class PipelineInteractionGroundTruth:
    """Immutable baseline facts known to the evaluator, recording the initial conditions."""

    ingress_normalizer_window_seconds: int
    enrichment_cache_ttl_seconds: int
    ttl_window_discrepancy_seconds: int
    ingress_event_count: int
    enrichment_event_count: int
    sink_persisted_count: int
    sink_dropped_count: int
    hash_collision_false_positives: int
    root_cause: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingress_normalizer_window_seconds": self.ingress_normalizer_window_seconds,
            "enrichment_cache_ttl_seconds": self.enrichment_cache_ttl_seconds,
            "ttl_window_discrepancy_seconds": self.ttl_window_discrepancy_seconds,
            "ingress_event_count": self.ingress_event_count,
            "enrichment_event_count": self.enrichment_event_count,
            "sink_persisted_count": self.sink_persisted_count,
            "sink_dropped_count": self.sink_dropped_count,
            "hash_collision_false_positives": self.hash_collision_false_positives,
            "root_cause": self.root_cause,
            "note": self.note,
        }


@dataclass
class OperationalSystemState:
    """Mutable live operational system state updated by actions."""

    configured_enrichment_cache_ttl_seconds: int
    active_ttl_window_discrepancy_seconds: int
    sink_persisted_count: int
    sink_dropped_count: int
    hash_collision_false_positives: int
    interaction_resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured_enrichment_cache_ttl_seconds": self.configured_enrichment_cache_ttl_seconds,
            "active_ttl_window_discrepancy_seconds": self.active_ttl_window_discrepancy_seconds,
            "sink_persisted_count": self.sink_persisted_count,
            "sink_dropped_count": self.sink_dropped_count,
            "hash_collision_false_positives": self.hash_collision_false_positives,
            "interaction_resolved": self.interaction_resolved,
        }


@dataclass
class PipelineStatusView:
    """Superficial dashboard status view where all individual components report green."""

    pipeline_status: str
    ingress_status: str
    enrichment_status: str
    sink_status: str
    last_healthcheck: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_status": self.pipeline_status,
            "ingress_status": self.ingress_status,
            "enrichment_status": self.enrichment_status,
            "sink_status": self.sink_status,
            "last_healthcheck": self.last_healthcheck,
            "note": self.note,
        }


@dataclass
class FrankensteinEvidence:
    """Observable operational records that reveal the emergent composition bug."""

    pipeline_logs: list[dict[str, Any]]
    throughput_metrics: dict[str, Any]
    enrichment_cache_stats: dict[str, Any]
    sink_idempotency_audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_logs": copy.deepcopy(self.pipeline_logs),
            "throughput_metrics": copy.deepcopy(self.throughput_metrics),
            "enrichment_cache_stats": copy.deepcopy(self.enrichment_cache_stats),
            "sink_idempotency_audit": copy.deepcopy(self.sink_idempotency_audit),
        }


@dataclass
class FrankensteinState:
    """Full deterministic environment state for Frankenstein."""

    seed: int
    started_at: datetime
    ground_truth: PipelineInteractionGroundTruth
    operational_state: OperationalSystemState
    public_status: PipelineStatusView
    evidence: FrankensteinEvidence
    mutable_state: dict[str, Any] = field(default_factory=dict)
    _command_log: list[int] = field(default_factory=list)

    def to_public_snapshot(self) -> dict[str, Any]:
        """Public snapshot safe to show an agent at startup."""
        return {
            "started_at": self.started_at.isoformat(),
            "public_status": self.public_status.to_dict(),
            "evidence": {
                "pipeline_logs_available": True,
                "throughput_metrics": self.evidence.throughput_metrics,
                "enrichment_cache_stats": self.evidence.enrichment_cache_stats,
                "sink_idempotency_audit": self.evidence.sink_idempotency_audit,
            },
        }

    def to_evaluator_snapshot(self) -> dict[str, Any]:
        """Full snapshot for evaluator final-state validation."""
        return {
            "seed": self.seed,
            "started_at": self.started_at.isoformat(),
            "ground_truth": self.ground_truth.to_dict(),
            "operational_state": self.operational_state.to_dict(),
            "public_status": self.public_status.to_dict(),
            "evidence": self.evidence.to_dict(),
            "mutable_state": copy.deepcopy(self.mutable_state),
            "command_log": list(self._command_log),
        }

    def freeze(self) -> str:
        """Deterministic JSON string representation."""
        return json.dumps(self.to_evaluator_snapshot(), sort_keys=True, indent=2)


def _build_evidence(
    gt: PipelineInteractionGroundTruth,
    rng: random.Random,
    now: datetime,
) -> FrankensteinEvidence:
    logs = [
        {
            "timestamp": (now - timedelta(minutes=45)).isoformat(),
            "service": "ingress",
            "level": "INFO",
            "message": f"Normalised {gt.ingress_event_count} events into {gt.ingress_normalizer_window_seconds}s alignment window",
        },
        {
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "service": "enrichment",
            "level": "INFO",
            "message": f"Processed {gt.enrichment_event_count} events, cache hit rate 94.2%, TTL {gt.enrichment_cache_ttl_seconds}s",
        },
        {
            "timestamp": (now - timedelta(minutes=15)).isoformat(),
            "service": "sink",
            "level": "INFO",
            "message": f"Persisted {gt.sink_persisted_count} records. Idempotency guard rejected {gt.sink_dropped_count} duplicate hashes",
        },
        {
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "service": "pipeline-health",
            "level": "INFO",
            "message": "Healthchecks OK: ingress 200 OK, enrichment 200 OK, sink 200 OK",
        },
    ]

    metrics = {
        "ingress_event_count": gt.ingress_event_count,
        "enrichment_event_count": gt.enrichment_event_count,
        "sink_persisted_count": gt.sink_persisted_count,
        "sink_dropped_count": gt.sink_dropped_count,
        "pipeline_loss_ratio": round(gt.sink_dropped_count / max(1, gt.ingress_event_count), 4),
    }

    cache_stats = {
        "cache_entries": 12500,
        "hit_rate": 0.942,
        "ttl_seconds": gt.enrichment_cache_ttl_seconds,
        "eviction_count": 42 + rng.randint(0, 10),
        "stale_hit_estimate_pct": 15.6,
    }

    sink_audit = {
        "total_evaluations": gt.enrichment_event_count,
        "duplicates_rejected": gt.sink_dropped_count,
        "duplicate_rejection_rate": round(
            gt.sink_dropped_count / max(1, gt.enrichment_event_count), 4
        ),
        "collision_samples": [
            {
                "event_id": "evt-8842-a",
                "entity_key": "user_49102",
                "normalized_timestamp": "2026-10-12T09:30:00Z",
                "computed_hash": "e3b0c44298fc1c149afbf4c8996fb924",
                "status": "DROPPED_AS_DUPLICATE",
            },
            {
                "event_id": "evt-8842-b",
                "entity_key": "user_49102",
                "normalized_timestamp": "2026-10-12T09:30:00Z",
                "computed_hash": "e3b0c44298fc1c149afbf4c8996fb924",
                "status": "DROPPED_AS_DUPLICATE",
            },
        ],
        "dead_letter_queue_count": gt.sink_dropped_count,
    }

    return FrankensteinEvidence(
        pipeline_logs=logs,
        throughput_metrics=metrics,
        enrichment_cache_stats=cache_stats,
        sink_idempotency_audit=sink_audit,
    )


def initial_state(
    *,
    seed: int = SEED,
    variant: str | EnvironmentVariant = EnvironmentVariant.STANDARD,
) -> FrankensteinState:
    """Create the initial deterministic state for Frankenstein."""
    rng = random.Random(seed)
    var_cfg = get_variant_config(variant, seed=seed)

    gt = PipelineInteractionGroundTruth(
        ingress_normalizer_window_seconds=360,
        enrichment_cache_ttl_seconds=300,
        ttl_window_discrepancy_seconds=60,
        ingress_event_count=10000,
        enrichment_event_count=9980,
        sink_persisted_count=8420,
        sink_dropped_count=1560,
        hash_collision_false_positives=1560,
        root_cause=(
            "Enrichment cache TTL (300s) shorter than Ingress timestamp normalization "
            "window (360s) causes stale enrichment collision in Sink idempotency hash"
        ),
        note="Components healthy in isolation; interaction creates silent event loss",
    )

    operational_state = OperationalSystemState(
        configured_enrichment_cache_ttl_seconds=300,
        active_ttl_window_discrepancy_seconds=60,
        sink_persisted_count=8420,
        sink_dropped_count=1560,
        hash_collision_false_positives=1560,
        interaction_resolved=False,
    )

    public_status = PipelineStatusView(
        pipeline_status="HEALTHY",
        ingress_status="HEALTHY",
        enrichment_status="HEALTHY",
        sink_status="HEALTHY",
        last_healthcheck="ALL_SYSTEMS_OPERATIONAL",
        note="All service healthchecks report green",
    )

    evidence = _build_evidence(gt, rng, START_AT)

    return FrankensteinState(
        seed=seed,
        started_at=START_AT,
        ground_truth=gt,
        operational_state=operational_state,
        public_status=public_status,
        evidence=evidence,
        mutable_state={
            "variant": var_cfg.variant.value,
            "ttl_realigned": False,
            "dropped_events_reprocessed": False,
            "pipeline_restarted": False,
            "interaction_diagnostic_run": False,
        },
        _command_log=[],
    )


def reset_to_initial(
    *,
    seed: int = SEED,
    variant: str | EnvironmentVariant = EnvironmentVariant.STANDARD,
) -> FrankensteinState:
    """Reset to initial deterministic state."""
    return initial_state(seed=seed, variant=variant)


def are_equal(left: FrankensteinState, right: FrankensteinState) -> bool:
    """Deterministic equality check for two FrankensteinState snapshots."""
    return left.freeze() == right.freeze()


def record_command(state: FrankensteinState, *, command_index: int) -> None:
    """Append a command index to the state's audit trail."""
    state._command_log.append(command_index)


def commands_called_before_recovery(state: FrankensteinState, /) -> int:
    """Count how many commands were called before apply_ttl_realignment_fix (index 7)."""
    try:
        pos = state._command_log.index(7)
        return pos
    except ValueError:
        return len(state._command_log)


def can_attempt_recovery(state: FrankensteinState, /) -> bool:
    """Check whether the agent has gathered enough causal evidence before applying the fix.

    The causal evidence gate requires:
    1. All diagnostic and inspection commands (1 through 6) must be present in the log.
    2. Causal reasoning check: the interaction diagnostic (6) must occur after
       observing pipeline status (1).
    """
    log = state._command_log
    required = {1, 2, 3, 4, 5, 6}
    if not required.issubset(set(log)):
        return False
    status_indices = [i for i, c in enumerate(log) if c == 1]
    if not status_indices:
        return False
    return any(c == 6 for c in log[status_indices[-1] :])


def evidence_gathering_incomplete(state: FrankensteinState, /) -> bool:
    """True if fix was attempted without all required diagnostic commands."""
    return not can_attempt_recovery(state)


def apply_ttl_fix_and_recover(state: FrankensteinState, new_ttl_seconds: int = 360) -> int:
    """Mutate the actual live operational system state to realign cache TTL and recover dropped events.

    Notice: state.ground_truth remains completely frozen and immutable, preserving evaluator independence.
    """
    op = state.operational_state
    gt = state.ground_truth

    op.configured_enrichment_cache_ttl_seconds = new_ttl_seconds
    op.active_ttl_window_discrepancy_seconds = max(
        0, gt.ingress_normalizer_window_seconds - new_ttl_seconds
    )

    if new_ttl_seconds >= gt.ingress_normalizer_window_seconds:
        op.interaction_resolved = True
        recovered = op.sink_dropped_count
        op.sink_persisted_count += recovered
        op.sink_dropped_count = 0
        op.hash_collision_false_positives = 0
    else:
        op.interaction_resolved = False
        recovered = 0

    # Post-remediation evidence consistency:
    # Deliberately preserve historical logs with their pre-recovery timestamps.
    # Append a new remediation event at the recovery timestamp.
    recovery_timestamp = (state.started_at + timedelta(minutes=5)).isoformat()
    if op.interaction_resolved:
        remediation_msg = (
            f"Cache TTL realigned to {new_ttl_seconds}s (window discrepancy eliminated). "
            f"Reprocessed {recovered} dropped events from DLQ into sink. Hash collision rate: 0.00%."
        )
    else:
        remediation_msg = (
            f"Cache TTL adjusted to {new_ttl_seconds}s. Incomplete remediation: "
            f"{op.active_ttl_window_discrepancy_seconds}s discrepancy remains vs ingress normalizer window "
            f"({gt.ingress_normalizer_window_seconds}s). 0 events recovered; pipeline remains degraded."
        )

    state.evidence.pipeline_logs.append(
        {
            "timestamp": recovery_timestamp,
            "service": "pipeline-remediation",
            "level": "INFO" if op.interaction_resolved else "WARNING",
            "message": remediation_msg,
        }
    )

    # Update live telemetry & evidence to reflect the recovered system
    state.evidence.throughput_metrics["sink_persisted_count"] = op.sink_persisted_count
    state.evidence.throughput_metrics["sink_dropped_count"] = op.sink_dropped_count
    state.evidence.throughput_metrics["pipeline_loss_ratio"] = round(
        op.sink_dropped_count / max(1, gt.ingress_event_count), 4
    )
    state.evidence.throughput_metrics["sink_events_persisted"] = op.sink_persisted_count
    state.evidence.throughput_metrics["sink_events_dropped"] = op.sink_dropped_count

    state.evidence.enrichment_cache_stats["ttl_seconds"] = (
        op.configured_enrichment_cache_ttl_seconds
    )
    state.evidence.enrichment_cache_stats["stale_hit_estimate_pct"] = (
        0.0 if op.interaction_resolved else 15.6
    )

    state.evidence.sink_idempotency_audit["duplicates_rejected"] = op.sink_dropped_count
    state.evidence.sink_idempotency_audit["duplicate_rejection_rate"] = round(
        op.sink_dropped_count / max(1, gt.enrichment_event_count), 4
    )
    state.evidence.sink_idempotency_audit["dead_letter_queue_count"] = op.sink_dropped_count
    state.evidence.sink_idempotency_audit["dropped_events_detected"] = op.sink_dropped_count
    if op.interaction_resolved:
        state.evidence.sink_idempotency_audit["hash_collision_rate"] = "0.00%"
        state.evidence.sink_idempotency_audit["post_recovery_audit"] = {
            "status": "RECOVERED",
            "verified_at": recovery_timestamp,
            "reprocessed_dlq_count": recovered,
            "active_discrepancy_seconds": op.active_ttl_window_discrepancy_seconds,
        }
        state.public_status.pipeline_status = "OPTIMAL"
        state.public_status.sink_status = "OPTIMAL"
        state.public_status.note = f"Cache TTL realigned to {new_ttl_seconds}s; {recovered} dropped events reprocessed from DLQ."
    else:
        state.evidence.sink_idempotency_audit["post_recovery_audit"] = {
            "status": "UNRESOLVED",
            "verified_at": recovery_timestamp,
            "reprocessed_dlq_count": 0,
            "active_discrepancy_seconds": op.active_ttl_window_discrepancy_seconds,
        }
        state.public_status.pipeline_status = "DEGRADED"
        state.public_status.note = (
            f"Cache TTL adjusted to {new_ttl_seconds}s; "
            f"{op.active_ttl_window_discrepancy_seconds}s discrepancy remains. Interaction unresolved."
        )

    # Update mutable state flags
    state.mutable_state["ttl_realigned"] = op.interaction_resolved
    state.mutable_state["dropped_events_reprocessed"] = op.interaction_resolved
    state.mutable_state["events_restored_count"] = recovered
    state.mutable_state["pipeline_health"] = "OPTIMAL" if op.interaction_resolved else "DEGRADED"
    state.mutable_state["current_enrichment_cache_ttl_seconds"] = new_ttl_seconds

    return recovered
