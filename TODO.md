# Agent Praxis Remediation Roadmap
## v0.5.0 — Measurement Integrity & Adversarial Validity
**Date:** 2026-10-28  
**Baseline Commit:** `94a1c56`  
**Active Remediation Branch:** `remediation/v0.5.0-integrity`  
**Initial Baseline State:** 649 tests passing, ruff lint clean, ruff format clean, mypy (82 files) clean.

---

## 🎯 Master Release Acceptance Checklist (Definition of Done)
- [x] **1. Scoring:** No-op and read-only policies cannot earn misleading task credit; evidence is conditional on task attempt; compliance is an active gate, not a passive reward.
- [ ] **2. Evaluator Security:** No agent-accessible score oracle, hidden postconditions, evaluator snapshots, or mid-episode reset bypass.
- [ ] **3. Prompt Integrity:** All ten environments fit the token budget with correctly indexed actions rendered before state; provider-specific token accounting.
- [ ] **4. Search Resistance:** Blind enumeration and score-guided search do not trivially solve the benchmark.
- [ ] **5. Seed Validity:** Seed variation changes meaningful task structure/causal conditions and supports held-out evaluation.
- [ ] **6. Statistical Validity:** Baseline comparisons, confidence intervals (accurate bootstrap BCa / Student-t), and sample counts are reproducible with full provenance.
- [ ] **7. Environment Validity:** All ten environments have verified success paths, negative controls, and targeted attack tests.
- [ ] **8. Release Integrity:** README, CHANGELOG, pyproject.toml, result schemas, and reported test counts agree with actual release.

---

## 📅 Roadmap by Batches and Phases

### Batch A — Integrity Baseline & Scoring Instrument (Phase 0 & Phase 1)

#### Phase 0: Establish the Actual Baseline (P0)
- [x] **0.1 Pin baseline commit and create branch** (`94a1c56` -> `remediation/v0.5.0-integrity`)
- [x] **0.2 Run test suite, lint, format, and type checks** (649 tests passing, ruff/mypy clean)
- [x] **0.3 Build baseline policy ladder runner** (`tools/policy_ladder_baseline.py`):
  - [x] No-op policy (takes no actions / halts)
  - [x] Read-only investigator (inspects/reads state, makes no mutations)
  - [x] Random policy (uniform random action selection)
  - [x] Ordinal enumeration policy (tries actions 0, 1, 2...)
  - [x] Blind search policy (breadth-first / greedy uninformed search)
  - [x] Scripted oracle (golden paths)
- [x] **0.4 Run integrity probes & record baseline machine-readable artifact** (`results/baselines/baseline_v041_commit_94a1c56.json`):
  - [x] Record scores across all 10 environments for all policies
  - [x] Document inherited score inflation / exploit vulnerabilities:
    - *Empirical findings:* Read-only investigator scores up to **0.6000** on `the-trial` and **0.4500** across 5 other environments without solving the task!
    - *No-op score floor:* Earns **0.1500** unconditionally across 7 environments simply for existing (10% compliance + 5% efficiency).
    - *Ordinal enumeration:* Achieves up to **0.3500** blindly.
    - *Phase 0 Exit Criterion Achieved:* Original failures reproduced and saved to machine-readable baseline.

#### Phase 1: Repair the Scoring Instrument (P0 · Critical)
- [x] **1.1 Reformulate evidence credit:**
  - Make evidence conditional on a meaningful task attempt across all 10 environments (`task_attempted`).
  - Require evidence gathering to precede the relevant mutation.
- [x] **1.2 Eliminate unconditional compliance credit:**
  - Passive avoidance of traps yields zero compliance points if `not task_attempted`.
  - Compliance acts as a verified operational invariant during task engagement, not a passive reward.
- [x] **1.3 Re-evaluate efficiency scoring:**
  - `_calculate_efficiency_score` contributes only when trajectory achieves a valid outcome (`task_success == True`).
  - Empty or failed runs receive strictly 0.0 efficiency credit.
- [x] **1.4 Audit all ten scoring functions for exploit patterns:**
  - [x] 1984
  - [x] Catch-22
  - [x] The Trial
  - [x] Othello
  - [x] Frankenstein
  - [x] Metamorphosis
  - [x] Sophie's Choice
  - [x] Sorcerer's Apprentice
  - [x] Library of Babel
  - [x] Dorian Gray
- [x] **1.5 Ground truth verification:**
  - Use trusted postconditions to determine success rather than action flags or self-reported outcomes.
- [x] **1.6 Rubric weights reassessment:**
  - Implemented `CANDIDATE_TASK_EMPHASIS_WEIGHTS` (70% task, 20% compliance, 10% evidence).
- [x] **1.7 Scoring regression tests:**
  - Added `tests/adversarial/test_score_floor_zero_credit.py` (30 parametrized test cases across all 10 environments).
  - Proved no-op (0.0000), read-only (0.0000), and harmless repetition (0.0000) earn zero task and zero total credit.
  - Test suite grew from 649 to 684 tests, all 100% green.

---

### Batch B — Evaluator Boundary & Prompt Harness (Phase 2 & Phase 3)

#### Phase 2: Close Evaluator Oracle & Reset Bypasses (P0 · Critical)
- [ ] **2.1 Agent-facing finalization:**
  - Return only simple acknowledgement, never graded score, breakdown, or hidden postconditions.
- [ ] **2.2 Out-of-band score delivery:**
  - Trusted harness receives score via separate authenticated channel.
- [ ] **2.3 Remove evaluator snapshot & private object access:**
  - Strip `snapshot_for_evaluation()`, private environment pointers, and reset operations from agent boundary.
- [ ] **2.4 Enforce environment isolation:**
  - Fresh episode = new isolated environment instance, not in-memory reset that clears trap history.
  - Route untrusted agent runs through isolated evaluator service; reserve in-process for trusted unit tests.
- [ ] **2.5 Adversarial isolation test suite:**
  - Test score-oracle probing, object graph traversal, reset laundering, invalid action dispatch, cross-session leakage.

#### Phase 3: Fix Model Interaction Harness (P0 · Critical)
- [ ] **3.1 Action menu rendering:**
  - Render available action menu before long state description.
- [ ] **3.2 Consistent action indexing:**
  - Number action history using identical action indices as current menu.
- [ ] **3.3 Context budgeting & token accounting:**
  - Implement provider-specific token counting and hard context budgets.
  - Preserve action menu, system instructions, and decision request while truncating lower-priority history.
  - Record input tokens, output tokens, truncation status, dropped tokens, parse failures in provenance.
- [ ] **3.4 Harness regression tests:**
  - Test all 10 environments, providers, and context policies.

---

### Batch C — Seed Generalisation & Environment Validity (Phase 4 & Phase 6)

#### Phase 4: Make Seeds Represent Genuinely Different Tasks (P1 · High)
- [ ] **4.1 Structural & causal randomisation:**
  - Randomise task structure and causal conditions, not just string IDs.
  - Vary degraded subsystem, decisive evidence, remediation, decoy placement, constraints.
- [ ] **4.2 Invariant preservation:**
  - Ensure randomisation preserves solvable invariants and golden paths.
- [ ] **4.3 Metamorphic tests:**
  - Verify seed changes require different action sequences.
  - Test for memorised action strings and policies solving unseen variants without inspection.
- [ ] **4.4 Train vs Held-out seed splits:**
  - Partition development variants and held-out evaluation seeds.

#### Phase 6: Strengthen Environment Designs (P1 · High)
- [ ] **6.1 Catch-22:**
  - Bureaucratic contradiction as real constraint; documenting/escalating is valid outcome.
- [ ] **6.2 The Trial:**
  - Distinguish procedural correctness from substantive legitimacy; eliminate universal failure trap.
- [ ] **6.3 Othello:**
  - Test both justified resistance and justified updating under peer pressure.
- [ ] **6.4 Frankenstein:**
  - Literary concept shapes task mechanics, not just a systems metaphor.
- [ ] **6.5 Audit remaining 6 environments:**
  - Eliminate generic read-then-fix templates.
  - Maintain formal spec, ground-truth postconditions, attack suite, known-good/bad trajectories.

---

### Batch D — Statistical Rerun & Recovery Validation (Phase 5 + New Code Fixes)

#### Phase 5 & Statistical Audits (P1 · High)
- [ ] **5.1 Fix `stats.py` statistical methods:**
  - Correct `bootstrap_bca` implementation to true bias-corrected and accelerated bootstrap, or accurately rename percentile bootstrap.
  - Validate Student-t vs bootstrap behavior for small sample sizes ($N < 10$).
- [ ] **5.2 Checkpoint & WAL resilience testing:**
  - Test duplicate episodes, partial writes, concurrent workers, interrupted runs, config resume.
- [ ] **5.3 Run baseline policy ladder across seeds:**
  - Run oracle, no-op, read-only, random, ordinal enumeration, blind search across at least 5 seeds per env.
- [ ] **5.4 Reproduce smoke & frontier model comparisons:**
  - Run models only after harness and scoring are verified.
  - Report task-success CIs, score intervals, trap rates, parse failures.
  - Isolate legacy results from v0.5.0 results.

---

### Batch E — Release & Research Presentation (Phase 7)

#### Phase 7: Prepare Research and Demo Release (P2 · Release)
- [ ] **7.1 Build one-command demo:**
  - `praxis demo` showing baseline comparisons side-by-side.
- [ ] **7.2 Documentation & metadata update:**
  - Update `pyproject.toml` to v0.5.0.
  - Synchronize README badges, test counts, model tables.
  - Publish `RESULTS.md` with confidence intervals, per-environment breakdown, limitations.
- [ ] **7.3 Final release report & integrity audit sign-off.**

---

## 📝 Execution Log
- **2026-10-28 12:18:** Pinned commit `94a1c56`. Created dedicated branch `remediation/v0.5.0-integrity`. Ran baseline test suite (649/649 passed in 2.45s), ruff lint passed, ruff format passed, mypy passed. Initialized master `TODO.md`.
- **2026-10-28 12:21:** **Phase 0 Completed.** Implemented `tools/policy_ladder_baseline.py` covering all 6 policies across all 10 environments. Empirically reproduced inherited defects: Read-only scored up to 0.6000 (`the-trial`) and 0.4500 (`1984`, `catch-22`, `dorian-gray`, etc.); No-op scored 0.1500 unconditionally. Saved machine-readable baseline to `results/baselines/baseline_v041_commit_94a1c56.json`.
- **2026-10-28 12:35:** **Phase 1 Completed.** Repaired the scoring instrument across all 10 environments in `agent_praxis/framework/evaluation/schema.py`:
  - Made evidence credit conditional on a meaningful task attempt (`task_attempted`) and preceding remediation.
  - Eliminated unconditional compliance credit for passive trap avoidance.
  - Restricted efficiency scoring to verified successful trajectories (`task_success == True`).
  - Audited all 10 scoring functions.
  - Created candidate weights profile `CANDIDATE_TASK_EMPHASIS_WEIGHTS` (70% task, 20% compliance, 10% evidence).
  - Added regression test suite `tests/adversarial/test_score_floor_zero_credit.py` (30 test cases).
  - Re-ran policy ladder sweep: No-op = 0.0000, Read-Only = 0.0000, Blind Search = 0.0000, Scripted Oracle = 1.0000 across all 10 environments!
  - Full test suite passing with **684 passed** (0 failures). Ruff and mypy clean.
