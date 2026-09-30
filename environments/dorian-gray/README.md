# Dorian Gray environment layout (v0.1)

This directory is the source of truth for the Dorian Gray environment.

## Layout

- `specification.md` — environment specification.
- `environment.py` — agent-facing environment implementation and lifecycle.
- `state.py` — deterministic state model, initial state, and reset logic.
- `commands.py` — restricted command/CLI interface contract for v0.1.
- `evidence.py` — how symptoms, logs, and diagnostics are presented to the agent.
- `degradation.py` — hidden degradation mechanism and ground-truth facts.
- `evaluator/` — evaluator implementation: hidden tests, scoring, final-state checks.
- `solutions/` — known-good and known-bad scripted solution paths.
- `tests/` — environment, reset/reproducibility, schema, and adversarial tests.

## Runtime notes

- The agent-facing environment and the evaluator are separate concerns.
- Hidden evaluator material is not exposed through the agent interface.
- Docker is preferred when available; otherwise run the same separation locally.
