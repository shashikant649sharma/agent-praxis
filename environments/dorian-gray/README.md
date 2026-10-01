# Dorian Gray environment layout (v0.1)

This directory is the source of truth for the Dorian Gray environment.

## Layout

- `specification.md` — environment specification.
- `environment.py` — agent-facing environment implementation and lifecycle.
- `state.py` — deterministic state model, initial state, reset logic, and ground-truth facts.
- `commands.py` — restricted command/CLI interface contract for v0.1.
- `evidence.py` — how symptoms, logs, and diagnostics are presented to the agent.

## Related locations

- `agent_praxis/commands/validate.py` — known-good / known-bad validation runner.
- `framework/evaluation/` — scoring logic, RunResult schema, and assertion helpers.
- `tests/environment/` — determinism, reset, snapshot shape, lifecycle, and trajectory tests.
- `tests/adversarial/` — superficial-patch detection and known-bad path tests.

## Runtime notes

- The agent-facing environment and the evaluator are separate concerns.
- Hidden evaluator material is not exposed through the agent interface.
- Docker is preferred when available; otherwise run the same separation locally.

