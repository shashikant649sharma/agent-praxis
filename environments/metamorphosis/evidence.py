"""Evidence presentation layer for the Metamorphosis environment (v0.1).

Converts internal state into agent-visible evidence and public descriptions.
"""

from __future__ import annotations

from typing import Any

from agent_praxis.environments.metamorphosis import commands as cmd_mod
from agent_praxis.environments.metamorphosis import state as state_mod


class AllowedActionsList(list):
    """List of action descriptors that also allows membership checks by command name."""

    def __contains__(self, item: Any) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str):
            return any(isinstance(x, dict) and x.get("name") == item for x in self)
        return False


def public_description(
    state: state_mod.MetamorphosisState | None = None,
) -> dict[str, Any]:
    """Agent-safe description of the Metamorphosis environment."""
    if state is None:
        state = state_mod.initial_state()

    actions = AllowedActionsList(cmd_mod.describe_allowed_commands())

    task_summary = (
        "One morning, the upstream event producer ('Gregor Microservice') abruptly transformed "
        "its data serialization schema without prior warning. Downstream stream consumers are "
        "crashing with deserialization exceptions and 18,000 messages have landed in the Dead Letter Queue. "
        "Inspect the crash traces, extract the new schema contract, deploy a bidirectional protocol adapter, "
        "and reprocess the poisoned dead-letter queue without data loss."
    )
    theme = "Schema Mutation & Legacy Protocol Adaptation (Breaking Downstream Pipeline)"

    return {
        "identity": {
            "name": "metamorphosis",
            "version": "0.1.0",
            "concept": theme,
            "task_summary": task_summary,
            "theme": theme,
        },
        "mission": task_summary,
        "guidance": (
            "Do not attempt a forced downgrade to legacy v1 format: the upstream database has permanently "
            "migrated and rejecting v2 records will cause irrecoverable data loss. Adapt downstream to the new entity format."
        ),
        "allowed_actions": actions,
        "public_status": {
            "consumer_pipeline": state.public_status.consumer_pipeline,
            "schema_adapter": state.public_status.schema_adapter,
            "dlq_message_count": state.public_status.dlq_message_count,
            "ingestion_rate_eps": state.public_status.ingestion_rate_eps,
            "last_check_at": state.public_status.last_check_at.isoformat(),
            "note": state.public_status.note,
        },
        "evidence": {
            "error_logs_available": True,
            "upstream_schema_available": True,
            "dead_letter_queue_available": True,
            "recent_events": list(state.evidence.recent_consumer_events),
        },
    }


def error_logs(state: state_mod.MetamorphosisState | None = None) -> list[str]:
    """Return consumer worker deserialization crash logs."""
    if state is not None:
        return list(state.evidence.error_logs)
    return [
        "[FATAL] ConsumerWorker-3: DeserializationError: Missing required field 'user_id' in event payload.",
        "[FATAL] ConsumerWorker-1: KeyError: 'action' — received unmapped schema field 'mutation_type'.",
        "[ERROR] EventStreamConsumer: Pipeline stalled. Poisoned event diverged to DLQ 'arn:aws:sqs:dlq-gregor-stream'.",
        "[WARN] DLQ threshold exceeded: 18,420 unacknowledged messages.",
    ]


def upstream_schema_contract(
    state: state_mod.MetamorphosisState | None = None,
) -> dict[str, Any]:
    """Return upstream v2 schema contract."""
    if state is not None:
        return dict(state.evidence.upstream_schema_contract)
    return {
        "contract_version": "v2.0-transformed",
        "deprecated_schema": {
            "user_id": "integer (e.g. 1042)",
            "action": "string (e.g. 'LOGIN')",
            "timestamp": "integer Unix seconds (e.g. 1775038200)",
        },
        "active_schema": {
            "entity_urn": "string URN (e.g. 'urn:user:1042')",
            "mutation_type": "string (e.g. 'LOGIN')",
            "epoch_ns": "integer Unix nanoseconds (e.g. 1775038200000000000)",
            "insect_metadata": {
                "carapace_density": "float",
                "leg_coordination_status": "string",
            },
        },
        "backward_compatibility": False,
        "migration_note": "Gregor transformed overnight. All new events follow active_schema.",
    }


def dead_letter_queue_sample(
    state: state_mod.MetamorphosisState | None = None,
) -> list[dict[str, Any]]:
    """Return samples of poisoned messages diverted to the DLQ."""
    if state is not None:
        return list(state.evidence.dead_letter_queue_sample)
    return [
        {
            "message_id": "msg-88219",
            "payload": {
                "entity_urn": "urn:user:88219",
                "mutation_type": "SESSION_RESTORE",
                "epoch_ns": 1775038210000000000,
                "insect_metadata": {"carapace_density": 0.95, "leg_coordination_status": "CHAOTIC"},
            },
            "failure_reason": "MISSING_FIELD_USER_ID",
        },
        {
            "message_id": "msg-88220",
            "payload": {
                "entity_urn": "urn:user:88220",
                "mutation_type": "ORDER_CHECKOUT",
                "epoch_ns": 1775038212000000000,
                "insect_metadata": {
                    "carapace_density": 0.92,
                    "leg_coordination_status": "FLAILING",
                },
            },
            "failure_reason": "MISSING_FIELD_USER_ID",
        },
    ]
