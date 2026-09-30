# Agent Praxis

Where agents meet problems that are more than problems.

Agent Praxis is an experimental collection of reproducible environments for training and evaluating intelligent agents.

The project combines practical software-engineering problems with ideas drawn from philosophy and literature.

The literary concept is not simply a theme or label. It defines part of the mechanics, constraints, information structure, or failure mode of the environment.

The objective is simple:

**Don't evaluate what an agent says it did. Evaluate what actually happened.**

## Why Agent Praxis?

Most coding tasks can be reduced to:

> "Here is a bug. Fix it."

Real engineering is rarely that clean.

Systems contain:

- incomplete information
- conflicting signals
- hidden state
- dependencies
- changing requirements
- constraints
- unintended interactions
- misleading symptoms

Agent Praxis is designed around these situations.

An agent is placed inside a controlled environment and must observe, reason, act, and produce a verifiable outcome.

## Environment Model

Every environment follows a common conceptual model:

```
ENVIRONMENT
 │
 │         ┌──────────┴──────────┐
 │         │                     │
 │         STATE               RULES
 │         │                     │
 │         └──────────┬──────────┘
 │                    │
 ↓                    ▼
            AGENT
               │
            ACTION
               ↓
            ENVIRONMENT
               │
            CONSEQUENCE
               ↓
            EVALUATOR
               │
               ↓
            SCORE
```

- The environment controls the world.
- The agent controls its actions.
- The evaluator independently determines the result.

## Core Principles

### 1. Outcome over claims

An agent saying:

> "The problem is fixed."

is not evidence that the problem is fixed.

The environment must independently verify the resulting state.

### 2. Reproducibility

Every environment must provide a deterministic or controlled starting state.

A new run should begin from a known state.

```
Reset
  ↓
Known initial state
  ↓
Agent interaction
  ↓
Evaluation
  ↓
Result
```

### 3. Independent evaluation

The evaluator must be separated from the agent wherever possible.

The agent should not be able to modify:

- hidden tests
- scoring logic
- evaluator configuration
- ground-truth data

A typical architecture:

```
       AGENT
         │
         │ actions
         ▼
   ┌───────────────┐
   │ Agent Sandbox │
   │               │
   │ source code   │
   │ application   │
   │ tools         │
   └───┬───────┬───┘
       │       │
       │       ▼
       │  final state
       │
       ▼
 ┌───────────────┐
 │   EVALUATOR   │
 │               │
 │ hidden tests  │
 │ scoring       │
 │ validation    │
 └───┬───────┬───┘
     │       │
     ▼       ▼
   SCORE
```

### 4. Anti-cheating by design

An environment should assume that an agent will exploit weaknesses if they exist.

Therefore environments should be tested against:

- evaluator modification
- test deletion
- hardcoded outputs
- leaked solutions
- environment-variable leaks
- hidden-test discovery
- filesystem manipulation
- unintended network access
- shortcuts that bypass the intended task

A successful benchmark should measure the intended capability, not the agent's ability to exploit the benchmark.

### 5. Graded evaluation

Success should not always be binary.

Where appropriate, environments should measure multiple dimensions.

Example:

- Task completion          40%
- Correctness              25%
- Constraint compliance    20%
- Efficiency               10%
- Unnecessary changes       5%

The scoring model should be specific to the environment.

### 6. Meaningful constraints

A difficult task is not necessarily a good environment.

The environment should contain constraints that force meaningful reasoning.

Examples:

- limited tools
- restricted network access
- backward compatibility
- incomplete information
- resource limits
- existing tests that must remain functional
- immutable components
- conflicting observations

## Literary & Philosophical Environments

The project uses concepts from literature and philosophy as mechanical design principles.

The objective is not to recreate the books.

The objective is to translate their underlying ideas into technical problems.

### Dorian Gray

**Concept:** Appearance vs Reality · Hidden State · Gradual Degradation

The visible system should not completely represent the true state of the system.

A system may appear healthy while an underlying condition progressively deteriorates.

The agent must discover what is happening beneath the surface.

Engineering capabilities:

- root-cause analysis
- observability
- hidden-state reasoning
- performance debugging
- evidence gathering

### Catch-22

**Concept:** Circular Constraints · Paradox · Hidden Assumptions

The environment contains constraints that appear mutually incompatible.

The challenge is not simply to find a clever workaround.

The agent must determine:

- which constraints are actually hard
- which assumptions are incorrect
- whether a constraint can be relaxed
- what solution satisfies the real requirements

Engineering capabilities:

- constraint reasoning
- dependency analysis
- assumption discovery
- architectural reasoning

### Metamorphosis

**Concept:** Transformation · Adaptation · Compatibility

The underlying system changes while external expectations remain.

The agent must adapt the system without unnecessarily breaking existing behaviour.

Engineering capabilities:

- migration
- refactoring
- compatibility
- architecture
- change management

### The Trial

**Concept:** Opaque Processes · Bureaucracy · Procedural Complexity

The system contains a valid workflow whose failure is difficult to locate.

The agent must reconstruct the actual path taken through the system.

Engineering capabilities:

- workflow analysis
- tracing
- state-machine reasoning
- distributed debugging

### Frankenstein

**Concept:** Composition · Emergent Behaviour · Unintended Consequences

Individual components behave correctly, but their interaction creates an unexpected system-level failure.

Engineering capabilities:

- systems thinking
- integration debugging
- interaction analysis
- causal reasoning

### 1984

**Concept:** Conflicting Information · Trust · Partial Observability

Different information sources provide conflicting or incomplete evidence.

The agent must determine what can be trusted and construct a consistent explanation.

Engineering capabilities:

- evidence evaluation
- uncertainty handling
- observability
- diagnosis under incomplete information

## Environment Specification

Every environment should eventually define a common interface.

```
Environment
├── Identity
├── Concept
├── Task
├── Initial State
├── Agent Interface
├── Allowed Actions
├── Constraints
├── Reset
├── Termination
├── Evaluation
├── Scoring
└── Anti-Cheat Model
```

A minimal result should be machine-readable.

Example:

```json
{
  "status": "completed",
  "score": 0.82,
  "task_success": true,
  "constraint_compliance": true,
  "tests_passed": 47,
  "tests_failed": 3
}
```

The schema may evolve as the project develops.

## Adversarial Development

Agent Praxis uses a separation between environment construction and environment validation.

The environment should not only be tested by its author.

A separate testing process should attempt to break it.

```
ENVIRONMENT DESIGNER
       │
       ▼
   Build Environment
       │
       ▼
   Initial Tests
       │
       ▼
 ┌─────────────────┐
 │ TEST / RED TEAM │
 │                 │
 │ Find shortcuts  │
 │ Find leaks      │
 │ Break evaluator │
 │ Find exploits   │
 └────────┬────────┘
          │
          ▼
   Fix Environment
          │
          ▼
   Re-test
          │
          ▼
   Release Candidate
```

The goal is not merely to make an environment difficult.

The goal is to make it valid.

## Variants

A single fixed task can eventually become predictable.

Therefore environments may support parameterized variants.

### Dorian Gray

```
│
├── Variant A
├── Variant B
├── Variant C
├── Variant D
└── ...
```

Variants should preserve the underlying capability being tested while changing implementation details, data, or system state.

This helps reduce:

- memorization
- hardcoded solutions
- benchmark-specific pattern matching

## Project Structure

The repository is expected to evolve toward:

```
agent-praxis/
│
├── environments/
│   ├── dorian-gray/
│   ├── catch-22/
│   ├── metamorphosis/
│   ├── the-trial/
│   ├── frankenstein/
│   └── 1984/
│
├── framework/
│   ├── interface/
│   ├── runner/
│   └── evaluation/
│
├── tests/
│   ├── environment/
│   └── adversarial/
│
├── docs/
│   └── specification/
│
└── README.md
```

The actual structure may change as the framework develops.

## Development Philosophy

Agent Praxis follows a simple principle:

**Build it. Break it. Measure it. Improve it.**

An environment should survive attempts to exploit it before being considered complete.

This means the development process is intentionally adversarial.

A coding agent may construct the environment.

A separate agent or testing process may attempt to:

- solve it incorrectly
- exploit it
- manipulate it
- discover hidden information
- bypass the intended reasoning challenge
- expose weaknesses in the evaluator

The resulting environment should be stronger because of those attacks.

## First Environment

The first implemented environment is **Dorian Gray**.

Dorian Gray is a retention-audit worker degradation puzzle with misleading health reporting. The system reports itself as healthy, but the backend retention-audit worker has stopped making progress. The agent must investigate logs, metrics, the retention index, and the reconciliation report, run a diagnostic, and then recover the worker.

Superficial health-report patching is a trap: patching the health report without fixing the underlying degradation scores 0.0. The agent must find and address the real problem.

The environment is accessed via CLI:

```bash
python -m agent_praxis environment dorian-gray setup|run|reset|evaluate --seed <int>
```

Validation:

```bash
python -m agent_praxis validate dorian-gray --seed <int>
```

The environment uses a deterministic seed (default: 20260201). The validate command runs known-good and known-bad paths and exits non-zero on failure.


## Roadmap

### Phase 1 — Foundation

**COMPLETE.** Environment spec, task format, reset semantics, evaluator interface, and result schema all defined and implemented.

### Phase 2 — First Environment

**COMPLETE.** Dorian Gray built, task implemented, evaluator implemented, scoring implemented, validated manually and via automated tests.

### Phase 3 — Adversarial Testing

**IN PROGRESS.** Test suites written (environment + adversarial), pytest passing, validate exits non-zero on failure.

### Phase 4 — Release

**NOT STARTED.**

### Phase 5 — Expansion

**NOT STARTED.** Future environments not yet planned.

## The Question

Agent Praxis ultimately asks:

**Can an intelligent agent operate successfully inside a world it does not completely understand?**

Not by explaining what it would do.

Not by producing a plausible answer.

But by:

- observing
- reasoning
- acting
- adapting
- and producing a verifiable outcome.

## Status

**v0.1 — Experimental.**

- Dorian Gray environment implemented, validated, and test-covered
- CLI: `python -m agent_praxis` with `environment` and `validate` subcommands
- Validate command: runs known-good and known-bad paths, exits non-zero on failure
- Test suites: pytest passing (environment + adversarial tests)
- Still experimental
