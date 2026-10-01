# Metamorphosis Environment Layout (v0.1)

This directory is the source of truth for the Metamorphosis environment.

## Layout

- `specification.md` — formal environment specification, silent schema mutation architecture, and scoring contract.
- `environment.py` — agent-facing environment implementation, step lifecycle, and audit trail tracking.
- `state.py` — deterministic state model, initial state generator, typed dataclasses (`SchemaMutationGroundTruth`, `PublicStatusView`, `MetamorphosisEvidence`, `MetamorphosisState`), and audit trail formatting.
- `commands.py` — restricted command/CLI allowlist contract (`AllowedCommand`, `CommandCategory`, parameter validation, and audit recording).
- `evidence.py` — state-aware evidence presentation, allowed actions formatted with metadata and backwards-compatible name lookup.

## Related Locations

- `agent_praxis/environments/metamorphosis/` — package export mirror.
- `agent_praxis/commands/validate.py` — known-good / known-bad validation runner (`validate_metamorphosis`).
- `framework/evaluation/schema.py` — enriched scoring logic (`_score_metamorphosis`) with 5-dimension breakdown and evidence gating.
- `tests/environment/test_metamorphosis_*.py` — deep state, commands, evidence, and scoring tests.
- `tests/environment/test_metamorphosis_validation.py` — validation harness tests.

## Runtime Notes

- An upstream system migrated schema versioning silently from v1 (legacy nested format) to v2 (flattened typed contract), breaking serialization while legacy health monitors continue to report OK.
- Superficial suppressions or raw data drops without establishing dual-schema adapter transformations score near 0.0.
- Legitimate resolution requires inspecting legacy schemas, analyzing wire payload discrepancies, developing a dual-schema compatibility adapter, validating idempotency, and committing the adapter migration.
