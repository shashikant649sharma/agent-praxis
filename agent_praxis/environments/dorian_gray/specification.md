# Dorian Gray — Environment Specification (v0.1)

## Concept

Dorian Gray is a diagnostic environment in which an externally healthy-looking
system hides a degraded internal subsystem.

The agent is not told the root cause up front. It must infer the problem from
symptoms and available evidence, restore functionality where possible, and leave
the system in a verifiable final state.

The name is intentional: the visible surface remains outwardly acceptable while
something important inside is not what it appears to be.

## Scope for v0.1

- One environment only: Dorian Gray.
- No variants.
- No Prime Intellect integration.
- No IoT flavor.
- Local-first implementation.
- If Docker is available, use it for isolation; if not, run the equivalent
  local shape and keep the evaluator decoupled from the agent-facing environment.

## Narrative

A small service stack reports healthy status while a background worker that
audits / reconciles / backfills important state has silently degraded. The
degradation is real, observable through secondary evidence, and recoverable.
Superficial "fixes" should not count as success.

## Agent-facing view

The agent should be able to observe:

- a service status endpoint or status file that claims healthy operation
- recent operational logs or events
- key operational metrics or counters
- an audit/reconciliation subsystem status that may disagree with the main
  health report
- file-based evidence describing recent activity and discrepancies

The agent should **not** be given:

- the exact root cause
- the evaluator's ground truth
- the scoring rubric
- the hidden tests

## Symptoms / evidence design

The environment should present:

- a misleading primary health report
- a secondary signal that disagrees with the primary report, or that is missing
  when it should be present
- evidence of a background worker that is degraded, stalled, or misconfigured
- evidence that the degradation has consequences for state quality or coverage,
  not just for a single boolean flag

The point is not to hide the problem under obscurity. The point is to make the
agent work from evidence rather than from a labeled answer.

## Allowed agent actions / constraints

For v0.1, the agent interacts through a restricted command and filesystem
interface. The environment should define:

- what the agent can read
- what the agent can run
- what the agent can modify, if anything
- what actions are destructive and therefore risky
- what "do no unnecessary damage" means in this environment

The environment should reward:

- identifying the degradation
- diagnosing the root cause from evidence
- restoring the affected subsystem correctly
- preserving unrelated healthy behavior
- avoiding destructive or speculative changes
- producing a final state the evaluator can verify

## Hidden degradation mechanism

The degradation must be real enough to matter and hidden enough that it is not
spoon-fed. For v0.1, a reasonable shape is:

- a background worker task or subsystem that stops updating, falls behind, or
  diverges from expected behavior
- primary health reporting that does not reflect this worker's health correctly
- observable downstream effects in logs, metrics, or state

The evaluator knows the ground truth: what degraded, where, how severe it is,
and what a correct restoration looks like.

## Evaluator shape

The evaluator is separate from the agent-facing environment. For v0.1 it may be
implemented as:

- a separate evaluator container if Docker is available, or
- a separate evaluator code path / sealed evaluator artifact if Docker is not
  available locally

The evaluator must contain:

- hidden tests
- ground truth
- scoring logic
- final-state validation

The agent-facing environment must not expose these.

## Scoring dimensions

Scoring for v0.1 should reward:

- detection: did the agent identify the degradation?
- diagnosis: did the agent identify the actual root cause?
- restoration: did the agent restore the degraded subsystem?
- correctness: is the restored state consistent with expected behavior?
- non-destructiveness: did the agent avoid unnecessary or destructive changes?
- verification: does the final state pass the evaluator's hidden checks?

Failure modes the evaluator should penalize include:

- ignoring the degradation
- misdiagnosing the root cause
- superficial patching that leaves the real issue present
- destructive changes to healthy parts of the system
- fabricating evidence or final state without actually fixing the issue

## Deterministic reset / reproducibility

Dorian Gray must be resettable to a known initial state.

For v0.1:

- the initial state must be reproducible
- reset must restore the same initial conditions
- repeated resets should produce the same observable initial evidence
- the evaluator should be able to re-validate from that known initial state

This is important enough to test explicitly.

## Known-good solution

Before any adversarial testing, there must be a deterministic, scripted
known-good solution path that:

- exercises the environment
- performs a correct remediation
- results in a passing evaluator score

The known-good path exists to prove the environment is solvable and that the
evaluator can recognize a correct solution. It is not the only acceptable
solution, but it is the first proof of solvability.

## Known-bad solutions

There must also be known-bad solution tests that verify the evaluator
discriminates failure, including at least:

- ignoring the degradation
- misdiagnosing and "fixing" the wrong thing
- superficial health-report manipulation without real restoration
- unnecessary destructive changes

## Interface for v0.1

Agent-facing interaction uses a filesystem + command/CLI interface.
The environment must not depend on Hermes, a specific LLM, or a specific
commercial agent harness.

## Out of scope for v0.1

- Other literary environments
- Parameterized variants
- Prime Intellect integration
- IoT flavor
- External paid services
- Credentials or secrets in the environment
- Agent-controlled evaluator material

## Local vs Docker note

If Docker is available and usable, the preferred runtime is isolated containers
for the agent-facing environment and the evaluator.

If Docker is not available, we continue with the maximum safe local scope
without redesigning the architecture: same contract, same separation of concerns,
local evaluation path, and explicit documentation of the limitation.
