# Agent Praxis — Final Implementation Decisions

Proceed with the approved architecture and project plan.

## Dorian Gray

Use a **background-worker degradation + misleading health reporting** mechanism.

The system should appear externally healthy while an internal subsystem gradually deteriorates. The agent must infer the underlying problem from observable evidence and restore the system.

Do not expose the ground truth directly. The environment must remain a genuine software-engineering diagnostic problem, not a hidden-answer puzzle.

## Agent Interface

Use a **filesystem + command/CLI interface** for v0.1.

Keep the interface simple and agent-agnostic. The environment must not depend on Hermes, a specific LLM, or a specific commercial agent.

Future adapters can expose the same environment through other agent harnesses.

## Evaluator Isolation

Use a **separate evaluator container** for v0.1.

The evaluator must contain:

- hidden tests
- ground truth
- scoring logic
- final-state validation

The agent container must not have access to these resources.

Evaluate the final environment state after the agent finishes.

## Development Validation

Before adversarial testing, create a known-good solution or scripted solution that demonstrates that the environment is actually solvable.

Validation sequence:

1. Build environment.
2. Verify deterministic reset.
3. Verify known initial state.
4. Verify known-good solution succeeds.
5. Verify known-bad solutions fail.
6. Verify evaluator produces correct scores.
7. Run coding agent.
8. Run adversarial/red-team agent.
9. Fix discovered weaknesses.
10. Repeat until stable.

## Development Autonomy

Proceed autonomously within the approved architecture. Do not pause for routine implementation decisions.

Request approval only for:

- major architectural changes
- changes to the environment concept
- security model changes
- external spending
- external service dependencies
- GitHub push / repository changes requiring credentials
- release decisions

## Prime Intellect

Keep the framework standalone and agent-agnostic. Do not couple the core architecture to Prime Intellect.

Implement Prime Intellect compatibility later through an adapter/integration layer after the standalone environment is validated.

## Variants

Do not implement variants in v0.1.

First validate the base Dorian Gray environment.

## Release

Dorian Gray is considered validated only when:

- Docker execution is reproducible
- reset is verified
- known-good solution succeeds
- known-bad solutions fail
- evaluator is isolated
- hidden tests are protected
- scoring is validated
- schema tests pass
- adversarial tests pass
- documentation exists
- sanitized example run exists

Do not treat "the code runs" as release-ready.

## First Implementation Sequence

Proceed in this order:

1. Foundation
2. Dorian Gray specification
3. Environment implementation
4. Known-good validation
5. Evaluation tests
6. Reset/reproducibility tests
7. Adversarial testing
8. Hardening
9. Documentation
10. Release candidate

Do not implement the other literary environments until Dorian Gray establishes that the framework and methodology work.
