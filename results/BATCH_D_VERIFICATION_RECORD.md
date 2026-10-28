# Batch D Statistical & WAL Reproducible Verification Record

- **Verification Date:** 2026-10-28T18:18:00Z
- **Statistical Implementation Milestone Commit:** `6909db7` (incorporating statistical fixes `68a1eb7`, `6990192`, `0bc5d08`)
- **Source Implementation & Artifact-Generation Commit:** `da17b0b`
- **Verification Record Update Commit:** `4472ac2`
- **Branch:** `remediation/v0.5.0-integrity`
- **Python Version:** Python 3.12.10
- **Pytest Version:** 9.1.1
- **Status:** **VERIFIED & AUDITED**

---

## 1. Test Suite & Code Quality Execution Summary

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Shashi\agent-praxis
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.1
collected 857 items

857 passed in 6.07s (0 failures, 0 warnings)
```

### Static Analysis & Types
- `python -m ruff check agent_praxis tests tools` : **All checks passed!**
- `python -m ruff format --check agent_praxis tests tools` : **173 files left unchanged (100% compliant)**
- `python -m mypy agent_praxis` : **Success: no issues found in 84 source files**

---

## 2. Statistical Hardening & Implementations

### 2.1 Tie-Aware BCa Bootstrap Bias Correction
In `agent_praxis.framework.runner.multiseed.stats._compute_bca_interval`:
- Benchmark scores on bounded discrete intervals frequently produce bootstrap replicate means identical to the observed sample mean.
- Implemented the tie-aware bootstrap proportion:
  $$\hat{p} = \frac{N_{<} + 0.5 N_{=}}{B}$$
  where $N_{<}$ is the count of replicates strictly below $\hat{\theta}$, $N_{=}$ is the count equal within $10^{-12}$, and $B$ is the number of bootstrap replicates.
- Symmetrically distributed or tied replicates yield $\hat{p} = 0.5$ and $z_0 = 0.0$, eliminating spurious bias inflation.

### 2.2 Dynamic Confidence Level Contract
In `agent_praxis.framework.runner.multiseed.stats`:
- **Input Validation:** Both `compute_continuous_score_ci` and `compute_wilson_score_interval` validate `0.5 < confidence_level < 1.0` and raise `ValueError` on out-of-bounds levels.
- **Student-t Quantiles:** `_get_student_t_critical(df, confidence_level)` uses:
  1. Standard library precomputed critical tables (`_STUDENT_T_CRITICAL_TABLE`) matching supported levels ($0.90, 0.95, 0.99$) within a strict float tolerance ($10^{-6}$).
  2. Cornish-Fisher expansion fallback for general/unsupported confidence levels (e.g. $0.954$).
  3. Optional `scipy.stats.t.ppf` when SciPy is present.
- **Wilson Score Interval:** Normal quantiles are derived dynamically via `statistics.NormalDist().inv_cdf(1.0 - (1.0 - confidence_level)/2.0)`.

### 2.3 Empirical Multi-Distribution Coverage Simulation
In `tests/runner/test_batch_d_statistical_and_wal_validation.py`:
- 100 Monte Carlo trials ($N=30$) across three distinct distribution families:
  1. **Symmetric (Uniform[0.2, 0.8]):** $95\%$ empirical coverage; Wilson CI $[0.8882, 0.9785]$ covers $0.95$.
  2. **Skewed Mixture (80% [0.1, 0.4] + 20% [0.7, 1.0]):** $93\%$ empirical coverage; Wilson CI $[0.8625, 0.9657]$ covers $0.95$.
  3. **Discrete Bounded with Ties ({0.0, 0.5, 1.0}):** $96\%$ empirical coverage; Wilson CI $[0.9016, 0.9843]$ covers $0.95$.

---

## 3. WAL Resilience & Concurrency Architecture Contract

### 3.1 Architectural Scope
In `agent_praxis.framework.runner.multiseed.checkpoint.CheckpointManager`:
- **Coroutine-Safe (Supported & Enforced):** Safe for concurrent asynchronous coroutines within a single coordinator process. An internal `asyncio.Lock`, explicit buffer flush, and `os.fsync()` guarantee atomic append serialization without interleaved records.
- **Single-Writer Coordinator:** MultiSeedExecutor operates as a single coordinator process. Multi-process concurrent writes to the same WAL file require external file locking or IPC coordination.
- **Crash & Truncation Recovery:** Corrupted or partial trailing lines (e.g. from power loss or kill signals) are skipped during startup replay while valid records are preserved and deduplicated by idempotency key.

---

## 4. Multi-Seed Policy Ladder Baseline Sweeps

All 6 canonical policies were evaluated across all 10 environments under three separate seed partition regimes. All sweeps were executed with generating commit `da17b0b`.

### 4.1 Canonical 5-Seed Full Sweep (300 Runs)
Machine-readable record: [`results/baselines/baseline_v050_canonical_300runs.json`](file:///d:/Shashi/agent-praxis/results/baselines/baseline_v050_canonical_300runs.json)
- Generating Commit: `da17b0b`
- Seeds: All 5 canonical seeds per environment from `DEFAULT_SEED_MAP` (3 development + 2 held-out).
- Total episodes: **300** (10 environments $\times$ 6 policies $\times$ 5 seeds).

```text
==========================================================================================
                              Policy Ladder Benchmark Sweep                               
==========================================================================================
Environment            No-Op      Read-Only    Random     Ordinal    BlindSearch  Oracle  
------------------------------------------------------------------------------------------
1984                   0.0000     0.0000       0.1200     0.3000     0.0000       1.0000  
catch-22               0.0000     0.0000       0.1800     0.3000     0.0000       1.0000  
dorian-gray            0.0000     0.0000       0.1700     0.3000     0.0000       1.0000  
frankenstein           0.0000     0.0000       0.0400     0.0000     0.0000       1.0000  
library-of-babel       0.0000     0.0000       0.0000     0.0000     0.0000       1.0000  
metamorphosis          0.0000     0.0000       0.2000     0.3000     0.0000       1.0000  
othello                0.0000     0.0000       0.1440     0.0000     0.0000       1.0000  
sophies-choice         0.0000     0.0000       0.0000     0.0000     0.0000       1.0000  
sorcerers-apprentice   0.0000     0.0000       0.0000     0.0000     0.0000       1.0000  
the-trial              0.0000     0.0000       0.0000     0.0000     0.0000       1.0000  
==========================================================================================
```

### 4.2 Development Split Sweep (180 Runs)
Machine-readable record: [`results/baselines/baseline_v050_development_180runs.json`](file:///d:/Shashi/agent-praxis/results/baselines/baseline_v050_development_180runs.json)
- Generating Commit: `da17b0b`
- Seeds: First 3 seeds per environment from `DEVELOPMENT_SEED_MAP`.
- Total episodes: **180** (10 environments $\times$ 6 policies $\times$ 3 seeds).
- Results: No-Op = **0.0000**, Read-Only = **0.0000**, Blind Search = **0.0000**, Scripted Oracle = **1.0000** across all 10 environments.

### 4.3 Held-Out Split Sweep (120 Runs)
Machine-readable record: [`results/baselines/baseline_v050_held_out_120runs.json`](file:///d:/Shashi/agent-praxis/results/baselines/baseline_v050_held_out_120runs.json)
- Generating Commit: `da17b0b`
- Seeds: Seeds 4 and 5 per environment from `HELD_OUT_SEED_MAP`.
- Total episodes: **120** (10 environments $\times$ 6 policies $\times$ 2 seeds).
- Results: No-Op = **0.0000**, Read-Only = **0.0000**, Blind Search = **0.0000**, Scripted Oracle = **1.0000** across all 10 environments.

### 4.4 Fixed 3-Seed Comparison Baseline (180 Runs)
Machine-readable record: [`results/baselines/verification_batch_d_commit_da17b0b.json`](file:///d:/Shashi/agent-praxis/results/baselines/verification_batch_d_commit_da17b0b.json)
- Generating Commit: `da17b0b`
- Seeds: `[42, 101, 2024]` across all 10 environments.
- Total episodes: **180** (10 environments $\times$ 6 policies $\times$ 3 seeds).
- Results: No-Op = **0.0000**, Read-Only = **0.0000**, Blind Search = **0.0000**, Scripted Oracle = **1.0000** across all 10 environments.

---

## 5. Invariant Assertion & Evidence Verification

### 5.1 Mechanical Invariant Assertions
All baseline sweeps enforce strict mechanical runtime assertions:
1. Every `(environment, policy)` pair contains exactly the set of expected seeds.
2. Incomplete or mismatched seed sets immediately trigger `AssertionError` preventing partial or distorted reporting.
3. Every policy run across all 6 policies (`noop`, `read_only`, `random`, `ordinal_enumeration`, `blind_search`, `scripted_oracle`) preserves complete per-run evidence:
   - `action_trace`: The full chronological list of executed action names (including `finalize`).
   - `scoring_breakdown`: The granular rubric breakdown dict (`evidence`, `task_completion`, `diagnosis`, `constraint_compliance`, `efficiency`).
   - `score`, `task_success`, `constraint_compliance`, `environment`, `seed`, `variant`.

### 5.2 Statistical Interpretation Note on Degenerate Intervals
Confidence intervals for all-zero ($0.0000$) and all-one ($1.0000$) sample sets collapse to a single point $[0.0, 0.0]$ and $[1.0, 1.0]$ respectively under the empirical degenerate sample guard. This accurately reflects the zero sample variance of the observed sample across these canonical seeds. It serves as an empirical sample property of the verified baseline, not an asymptotic mathematical claim that the true population failure or success rate is exactly 0% or 100% across infinite out-of-distribution seeds.

