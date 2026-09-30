# Agent Praxis — Foundation

This directory defines the shared contract that all environments and the evaluator build on.

Guiding rule: keep the foundation thin and agent-agnostic. Environments and runners
consume this contract; they do not own it.

## Pieces

- `environment/contract.py` — environment identity, lifecycle, and interface contract.
- `runner/helpers.py` — setup / run / reset / evaluate wiring for local (and future Docker)
  execution.
- `evaluation/schema.py` — machine-readable result schema and basic validation helpers.
- `evaluation/validation.py` — known-good / known-bad validation helpers and evaluation checks.

## Design intent

- The agent sees an environment interface and a restricted command surface.
- The evaluator sees ground truth, hidden tests, and final-state validation.
- The framework never assumes a specific agent harness, LLM, or orchestration layer.
- Docker is the preferred runtime for isolation, but the foundation must still be coherent
  when Docker is unavailable locally.
