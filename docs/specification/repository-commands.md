# Repository commands

This document describes the intended repo-level commands for Agent Praxis.

The exact command surface may evolve, but the responsibilities below should remain stable.

## Setup

Recommended local setup:

```bash
uv sync --extra dev
```

If `uv` is not available on the machine, install dependencies from `pyproject.toml` using the project's normal Python tooling.

## Linting

```bash
ruff check .
ruff format . --check
```

## Tests

Run all tests:

```bash
pytest
```

Run environment tests:

```bash
pytest tests/environment
```

Run adversarial tests:

```bash
pytest tests/adversarial
```

## Validation

Validate an environment end-to-end:

```bash
python -m agent_praxis validate dorian-gray
```

A validation run should exercise, at minimum:

- environment startup
- deterministic reset
- known-good solution path
- known-bad solution path
- evaluator execution
- result schema validation

## Environment commands

Each environment should eventually support commands similar to:

```bash
python -m agent_praxis environment dorian-gray setup
python -m agent_praxis environment dorian-gray run
python -m agent_praxis environment dorian-gray reset
python -m agent_praxis environment dorian-gray evaluate
```

The agent interface is not required to use these directly. They exist so the repository can run, inspect, and validate environments without depending on any specific agent harness.

## Adversarial testing

Adversarial tests are run separately because they are intentionally destructive where needed.

```bash
pytest tests/adversarial
```

Adversarial tests should be written as attack probes, not as normal happy-path tests.

## Manual inspection

For v0.1, some things may still be easier to inspect manually in Docker. That is acceptable as long as the automated checks cover the release gates.

## Future commands

Later, the project may add:

- environment packaging commands
- variant generation
- benchmarking helpers
- Prime Intellect adapter commands

Those are not part of v0.1.
