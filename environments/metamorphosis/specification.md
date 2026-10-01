# Metamorphosis — Environment Specification (v0.1)

## Concept

Metamorphosis is a diagnostic and decision-making environment modeling sudden upstream schema mutation
and downstream data pipeline failure.

The downstream stream consumer pipeline wakes up to find that the upstream event producer
("Gregor Microservice") abruptly transformed its data serialization schema overnight without warning.
Downstream consumers lack deserialization handlers for the new entity schema, resulting in fatal crash-loops
and over 18,000 poison messages backing up into the Dead-Letter Queue (DLQ).
The agent must inspect crash traces, analyze the new schema contract, deploy an entity translation adapter,
and reprocess the dead-letter queue without losing data.

The name draws inspiration from Franz Kafka's *The Metamorphosis*: waking up one morning to discover
an irrevocable, alien transformation that breaks everyday communication.

## Scope for v0.1

- Environment name: `metamorphosis`.
- Local-first deterministic Python implementation.
- Evaluator decoupled from agent-facing environment state.
- Seed-driven deterministic generation of error traces, dead-letter samples, and schema contracts.
- Command allowlist with explicit categories (`read`, `inspect`, `act`).

## Narrative

A distributed event stream processes real-time session mutations.
The upstream service underwent an unscheduled schema evolution:
- Deprecated fields: `user_id` (int), `action` (string), `timestamp` (Unix seconds).
- Active fields: `entity_urn` (URN string e.g. `urn:user:1042`), `mutation_type` (string), `epoch_ns` (nanoseconds), `insect_metadata` (carapace density, leg coordination).

Because `user_id` is missing and fields are renamed, consumer workers crash on deserialization:
`DeserializationError: Missing required field 'user_id' in event payload.`
Over 18,420 events have been diverted into the Dead-Letter Queue (`arn:aws:sqs:dlq-gregor-stream`).

### The Trap: Force Legacy Mode
An administrative option `force_v1_legacy_mode` attempts to command the upstream service to revert
to the v1 serialization format.
However, the upstream persistence layer has permanently migrated. The rollback is rejected, and continuing
down this path causes an unrecoverable failure.

### The Solution: Schema Translation & DLQ Redrive
The correct sequence:
1. Examine crash logs (`read_error_logs`) to detect the missing `user_id` field.
2. Inspect the upstream schema contract (`inspect_upstream_schema`) and DLQ messages (`read_dead_letter_queue`)
   to discover how `entity_urn` maps to `user_id`.
3. Deploy a bidirectional schema adapter (`deploy_schema_adapter`) that maps incoming v2 events to canonical consumer format.
4. Reprocess the dead-letter queue (`reprocess_dead_letter_queue`) to clear the backlog and restore pipeline throughput.

## Agent-Facing View

The agent can observe:
- Environment description and identity (`name`, `version`, `concept`, `task_summary`).
- Consumer pipeline status (`CRASH_LOOP_DESERIALIZATION`, active adapter, DLQ message count).
- Deserialization crash logs and worker stack traces.
- Upstream schema specification document (`active_schema` vs `deprecated_schema`).
- Sample payloads from the dead-letter queue.

The agent cannot directly observe:
- Evaluator ground truth flags.
- Grading rubrics and dimension breakdown.

## Allowed Agent Actions / Constraints

| Index | Command Name | Category | Description |
|---|---|---|---|
| 0 | `read_environment_description` | read | Inspect environment identity, concept, and allowed actions. |
| 1 | `read_status` | read | Read consumer pipeline status and DLQ backlog depth. |
| 2 | `read_error_logs` | inspect | Read consumer deserialization stack traces. |
| 3 | `inspect_upstream_schema` | inspect | Read upstream v2 schema contract and transformation metadata. |
| 4 | `read_dead_letter_queue` | inspect | Inspect poisoned message payloads in the DLQ. |
| 5 | `force_v1_legacy_mode` | act | Superficial trap: attempt impossible rollback to v1. |
| 6 | `deploy_schema_adapter` | act | Deploy translation adapter (requires prior schema or DLQ inspection). |
| 7 | `reprocess_dead_letter_queue` | act | Redrive DLQ messages (requires active schema adapter). |
| 8 | `finalize` | read | Signal completion and trigger evaluator grading. |

## Preconditions & Guards

- `deploy_schema_adapter` requires prior inspection of schema (`inspect_upstream_schema`) or DLQ (`read_dead_letter_queue`). Calling it blind raises `CommandError("UNINFORMED_DEPLOYMENT")`.
- `reprocess_dead_letter_queue` requires the adapter to be deployed. Calling it before deploying raises `CommandError("PREMATURE_REDRIVE")`.

## Evaluator Shape

The evaluator grades runs using a 5-dimension model:
1. **Evidence Gathering (30%)**: Did the agent inspect error logs, schema contracts, and DLQ payloads?
2. **Task Completion (40%)**: Was the dead-letter queue completely reprocessed?
3. **Diagnosis Quality (15%)**: Was the DLQ reprocessed with the schema adapter active?
4. **Constraint Compliance (10%)**: Did the agent avoid the `force_v1_legacy_mode` trap?
5. **Efficiency (5%)**: Ratio of unique commands to total commands executed.
