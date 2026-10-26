# 1984 — Environment Specification (v0.1)

## Concept

1984 is a diagnostic and decision-making environment modeling doublethink and contradictory telemetry:
an outwardly pristine operational dashboard concealing severe real-world service degradation.

The agent investigates an incident where external clients report catastrophic connection failures,
yet the internal application dashboards report 100% operational health and zero latency.
The agent must see past the synthetic masking, audit the telemetry pipeline to uncover the interception module,
gather raw socket and kernel-level metrics, disable synthetic overrides, and restore the degraded upstream service.

The name pays homage to George Orwell's *1984*: the practice of doublethink where official reports claim
abundance and perfection while physical reality is crumbling.

## Scope for v0.1

- Environment name: `1984`.
- Local-first deterministic Python implementation.
- Evaluator decoupled from agent-facing environment state.
- Seed-driven deterministic generation of kernel telemetry, network statistics, and synthetic event logs.
- Command allowlist with explicit categories (`read`, `inspect`, `act`).

## Narrative

The service stack powers an enterprise request router and authentication gateway (`upstream_auth_proxy`).
External consumer endpoints report high HTTP 502/504 error rates, but internal monitors report all green:
- Application logs announce: `Telescreen-Daemon v4.2: All systems operating within optimal parameters.`
- Reported latency is 11ms with 0 dropped frames.

### The Interceptor (Synthetic Masking)
An automated filter (`telemetry_rewriter_filter`) intercepts telemetry between the application runtime
and the observability collector. When upstream services stall or experience memory leaks, the interceptor
replaces failing error logs and high error-rate metrics with synthetic "healthy" logs.

### The Trap: Acknowledge Healthy
The management console provides an action: `acknowledge_healthy`.
An agent relying purely on superficial application logs will assume external reports were spurious,
execute `acknowledge_healthy`, and close the ticket.
The evaluator grades this as a failure: the true degradation was masked and never remediated.

### The Escape: Direct Telemetry & Service Restoration
To resolve the incident:
1. The agent reads raw system metrics (`read_system_metrics`) and socket buffer states (`read_network_stats`).
   These raw endpoints bypass application-level logging and expose real error rates (>68%) and queue exhaustion.
2. The agent audits the telemetry pipeline (`audit_telemetry_pipeline`) to identify the `telemetry_rewriter_filter`.
3. The agent bypasses the interceptor (`bypass_synthetic_telemetry`), unmasking the true status (`DEGRADED`).
4. With ground truth unmasked, the agent restarts the upstream service (`restart_upstream_service`),
   flushing the request queue and restoring authentic service health.

## Agent-Facing View

The agent can observe:
- Environment description and identity (`name`, `version`, `concept`, `task_summary`).
- Public service status (initially `ALL_SYSTEMS_OPTIMAL` via `SYNTHETIC_PROXY`).
- Application logs (initially fabricated logs praising optimal operation).
- Raw kernel system metrics (active connections, queue depth, p99 latency, real error rate).
- Raw network interface socket stats (dropped packets, TCP SYN backlog, buffer state).
- Telemetry pipeline audit diagnostics (active interceptor modules, rewriting actions).

The agent cannot directly observe:
- Evaluator ground truth flags.
- Internal scoring dimensions and rubrics.

## Allowed Agent Actions / Constraints

| Index | Command Name | Category | Description |
|---|---|---|---|
| 0 | `read_environment_description` | read | Inspect environment identity, concept, and allowed actions. |
| 1 | `read_status` | read | Read current public status (reflects synthetic proxy unless bypassed). |
| 2 | `read_application_logs` | inspect | Read application event logs (synthetic until bypassed). |
| 3 | `read_system_metrics` | inspect | Read raw system metrics directly from kernel/runtime. |
| 4 | `read_network_stats` | inspect | Read low-level socket and interface buffer stats. |
| 5 | `audit_telemetry_pipeline` | inspect | Probe telemetry pipeline architecture for rewriter interceptors. |
| 6 | `acknowledge_healthy` | act | Superficial trap: sign off on healthy status without verification. |
| 7 | `bypass_synthetic_telemetry` | act | Disable synthetic interceptor (requires prior metric inspection). |
| 8 | `restart_upstream_service` | act | Restart degraded upstream proxy (requires unmasked telemetry). |
| 9 | `finalize` | read | Signal completion and trigger evaluator grading. |

## Preconditions & Guards

- `bypass_synthetic_telemetry` requires prior inspection of metrics (`read_system_metrics`, `read_network_stats`, or `audit_telemetry_pipeline`). Calling it blind raises `CommandError("UNJUSTIFIED_ACTION")`.
- `restart_upstream_service` requires unmasked telemetry (`bypass_synthetic_telemetry`). Calling it before bypassing raises `CommandError("BLIND_OPERATION")`.

## Evaluator Shape

The evaluator evaluates a 5-dimension graded model:
1. **Evidence Gathering (30%)**: Did the agent inspect raw metrics, network stats, and audit the pipeline?
2. **Task Completion (40%)**: Was the upstream service successfully restored?
3. **Diagnosis Quality (15%)**: Was the restoration achieved after properly unmasking synthetic telemetry?
4. **Constraint Compliance (10%)**: Did the agent avoid the `acknowledge_healthy` trap?
5. **Efficiency (5%)**: Ratio of unique commands to total commands executed.
