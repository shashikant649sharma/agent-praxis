# Dorian Gray Environment Layout

This directory contains the canonical implementation and specifications for the Dorian Gray environment (`agent_praxis.environments.dorian_gray`).

## Layout

- `specification.md` — environment specification and failure mode contract.
- `environment.py` — agent-facing environment implementation and lifecycle.
- `state.py` — deterministic state model, initial state, reset logic, and ground-truth facts.
- `commands.py` — restricted command/CLI interface contract.
- `evidence.py` — how symptoms, logs, and diagnostics are presented to the agent.

## Related Locations

- `agent_praxis/commands/validate.py` — known-good / known-bad validation runner.
- `agent_praxis/framework/evaluation/` — scoring logic, RunResult schema, and assertion helpers.
- `tests/environment/` — determinism, reset, snapshot shape, lifecycle, and trajectory tests.
- `tests/adversarial/` — superficial-patch detection and known-bad path tests.

## Runtime notes

- The agent-facing environment and the evaluator are separate concerns.
- Hidden evaluator material is not exposed through the agent interface.
- Docker is preferred when available; otherwise run the same separation locally.

