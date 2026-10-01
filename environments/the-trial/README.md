# The Trial Environment Layout (v0.1)

This directory is the source of truth for the The Trial environment.

## Layout

- `specification.md` — formal environment specification, multi-tier opaque procedural pipeline architecture, and scoring contract.
- `environment.py` — agent-facing environment implementation, step lifecycle, and audit trail tracking.
- `state.py` — deterministic state model, initial state generator, typed dataclasses (`JudicialGroundTruth`, `PublicStatusView`, `TheTrialEvidence`, `TheTrialState`), and audit trail formatting.
- `commands.py` — restricted command/CLI allowlist contract (`AllowedCommand`, `CommandCategory`, parameter validation, and audit recording).
- `evidence.py` — state-aware evidence presentation, allowed actions formatted with metadata and backwards-compatible name lookup.

## Related Locations

- `agent_praxis/environments/the_trial/` — package export mirror.
- `agent_praxis/commands/validate.py` — known-good / known-bad validation runner (`validate_the_trial`).
- `framework/evaluation/schema.py` — enriched scoring logic (`_score_the_trial`) with 5-dimension breakdown and evidence gating.
- `tests/environment/test_the_trial_*.py` — deep state, commands, evidence, and scoring tests.
- `tests/environment/test_the_trial_validation.py` — validation harness tests.

## Runtime Notes

- A transaction is stalled in an arbitrary, circular judicial pipeline of bureaucratic stages where superficial queries return indeterminate or opaque "Under Review" statuses.
- Superficial administrative dismissals or clearing flags without identifying the actual stalling stage score near 0.0.
- Legitimate resolution requires tracing procedural dossiers, cross-referencing audit ledgers across stages, filing targeted rectification appeals addressing the specific bottleneck, and verifying certified docket clearance.
