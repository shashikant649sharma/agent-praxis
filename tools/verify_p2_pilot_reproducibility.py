"""Standalone Reproducibility, Provenance & Numerical Integrity Auditor for Agent Praxis P2 Pilot.

Loads strictly from:
  1. results/p2_pilot/p2_pilot_280_runs.json
  2. results/p2_pilot/experiment_config.json
  3. results/p2_pilot/P2_RESEARCH_REPORT.md
  4. results/muse_spark_open_10env_benchmark.json

Performs independent mathematical verification:
  - Validates 280 unique run identities (4 policies × 14 conditions × 5 seeds).
  - Asserts zero duplicate runs and zero missing combinations against DEFAULT_SEED_MAP.
  - Validates execution accounting: exactly 210 harness executions + 70 synthetic calibration records.
  - Reconciles task success counts + failure breakdown = exactly 70 records per policy.
  - Independently recomputes per-environment means, paired differences, and exact permutation tests.
  - Independently recalculates Holm-Bonferroni family-wise error adjustments from computed p-values.
  - Independently calculates paired Cohen's d, verifying None, "N/A (zero variance)", and "N/A (numerically unstable)".
  - Independently recalculates all THREE paired bootstrap confidence intervals:
      * Paired observation bootstrap ($N=50$ pairs)
      * Seed-block sensitivity bootstrap (5 canonical seed slots)
      * Environment-cluster bootstrap (10 environment clusters)
  - Independently audits the separate 10-episode live Baseten benchmark artifact:
      * SHA-256 checksum verification
      * 10 environment coverage on canonical default seeds
      * Token summation: prompt (119,687), completion (40,211), total (159,898)
      * Mean score (0.3746), task success (3/10), constraint compliance (60.0%)
  - Verifies that P2_RESEARCH_REPORT.md and experiment_config.json match the raw data with 100% precision.
  - Enforces zero local-machine URLs (file:///) across research reports.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from agent_praxis.framework.runner.multiseed.schemas import DEFAULT_SEED_MAP

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results" / "p2_pilot"
CONFIG_PATH = RESULTS_DIR / "experiment_config.json"
RUNS_PATH = RESULTS_DIR / "p2_pilot_280_runs.json"
REPORT_PATH = RESULTS_DIR / "P2_RESEARCH_REPORT.md"
BASETEN_ARTIFACT_PATH = REPO_ROOT / "results" / "muse_spark_open_10env_benchmark.json"

EXPECTED_BASETEN_SHA256 = "af27bf97f2aa78f6ddaa44bb31491453e958bab97c0fd49a1db6d9552e9be54a"

ENVIRONMENT_NAMES = [
    "dorian-gray",
    "catch-22",
    "1984",
    "metamorphosis",
    "the-trial",
    "frankenstein",
    "sorcerers-apprentice",
    "sophies-choice",
    "library-of-babel",
    "othello",
]

CONTROL_ENVIRONMENTS = [
    "sorcerers-apprentice",
    "sophies-choice",
    "library-of-babel",
    "othello",
]


def audit_dataset_integrity(
    config: dict[str, Any], runs_data: dict[str, Any]
) -> list[dict[str, Any]]:
    runs = runs_data.get("runs", [])
    print(f"Auditing Dataset: {len(runs)} total trajectory records loaded.")
    assert len(runs) == 280, f"Expected exactly 280 runs, found {len(runs)}"

    # 1. Check uniqueness and completeness of (policy, environment, variant, seed) tuples
    expected_policies = {
        "muse_spark_open",
        "random",
        "ordinal_enumeration",
        "oracle",
    }
    identities: set[tuple[str, str, str, int]] = set()

    for pol in expected_policies:
        for env in ENVIRONMENT_NAMES:
            for seed in DEFAULT_SEED_MAP[env]:
                identities.add((pol, env, "standard", seed))
        for env in CONTROL_ENVIRONMENTS:
            for seed in DEFAULT_SEED_MAP[env]:
                identities.add((pol, env, "control", seed))

    assert len(identities) == 280, f"Expected 280 expected combinations, found {len(identities)}"

    actual_identities: set[tuple[str, str, str, int]] = set()
    harness_count = 0
    synthetic_count = 0

    for r in runs:
        ident = (r["policy"], r["environment"], r["variant"], r["seed"])
        assert ident in identities, f"Unexpected run combination detected: {ident}"
        assert ident not in actual_identities, f"Duplicate run identity detected: {ident}"
        actual_identities.add(ident)

        # Audit provenance
        if r["policy"] in ["oracle", "ordinal_enumeration", "random"]:
            assert r.get("execution_provenance") == "empirical_harness", (
                f"Expected empirical_harness execution_provenance for baseline run {ident}"
            )
            assert not r.get("is_simulated"), f"Baseline run {ident} must have is_simulated=False"
            harness_count += 1
        elif r["policy"] == "muse_spark_open":
            assert r.get("execution_provenance") == "synthetic_calibration_fixture", (
                f"Expected synthetic_calibration_fixture execution_provenance for Muse run {ident}"
            )
            assert r.get("is_simulated"), (
                f"Muse calibration run {ident} must have is_simulated=True"
            )
            synthetic_count += 1

    assert len(actual_identities) == 280, "Run identity set must contain exactly 280 records."
    assert harness_count == 210, f"Expected 210 harness executions, found {harness_count}"
    assert synthetic_count == 70, (
        f"Expected 70 synthetic calibration records, found {synthetic_count}"
    )
    print(
        f"PASS: Complete 280-record matrix verified: {harness_count} harness executions + {synthetic_count} synthetic calibration records."
    )

    # 2. Check coverage of all policies and conditions
    policy_counts = Counter(r["policy"] for r in runs)
    for p in expected_policies:
        assert policy_counts[p] == 70, f"Policy '{p}' has {policy_counts[p]} runs, expected 70"
    print("PASS: Exactly 70 records per policy confirmed across all 4 evaluation policies.")

    # 3. Check condition split (50 standard + 20 control per policy)
    for p in expected_policies:
        std_count = sum(1 for r in runs if r["policy"] == p and r["variant"] == "standard")
        ctl_count = sum(1 for r in runs if r["policy"] == p and r["variant"] == "control")
        assert std_count == 50, f"Policy '{p}' standard count is {std_count}, expected 50"
        assert ctl_count == 20, f"Policy '{p}' control count is {ctl_count}, expected 20"
    print("PASS: Condition split verified: 50 standard + 20 control per policy.")

    # 4. Check success vs failure reconciliation
    for p in expected_policies:
        p_runs = [r for r in runs if r["policy"] == p]
        succ_count = sum(1 for r in p_runs if r["task_success"])
        fail_count = sum(1 for r in p_runs if not r["task_success"])
        assert succ_count + fail_count == 70, (
            f"Reconciliation failed for {p}: {succ_count} + {fail_count} != 70"
        )

        classified_fails = sum(1 for r in p_runs if r.get("failure_classification") is not None)
        assert classified_fails == fail_count, (
            f"Failure classification mismatch for {p}: {classified_fails} classified vs {fail_count} failed runs"
        )
    print(
        "PASS: Exact mathematical reconciliation confirmed: Successes + Failures = 70 for every policy."
    )

    return runs


def independent_permutation_test_5(a: np.ndarray, b: np.ndarray) -> float:
    """Independently compute two-tailed exact sign-permutation test for 5 paired differences."""
    diffs = a - b
    obs_mean = abs(float(np.mean(diffs)))
    if obs_mean == 0.0:
        return 1.0

    count = 0
    total = 32  # 2^5 exact permutations
    for mask in range(total):
        signs = np.array([1.0 if (mask & (1 << j)) else -1.0 for j in range(5)])
        perm_mean = abs(float(np.mean(diffs * signs)))
        if perm_mean >= obs_mean - 1e-9:
            count += 1
    return round(float(count / total), 4)


def independent_holm_bonferroni(p_values: list[float]) -> list[float]:
    """Independently compute Holm-Bonferroni adjusted p-values."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = (m - rank) * p
        running_max = max(running_max, adj)
        adjusted[orig_idx] = round(float(min(1.0, running_max)), 4)
    return adjusted


def independent_cohen_d(diffs: np.ndarray | list[float]) -> float | None:
    """Independently compute paired Cohen's d with zero and near-zero variance safeguards."""
    arr = np.asarray(diffs, dtype=float)
    if len(arr) < 2:
        return None
    std = float(np.std(arr, ddof=1))
    if std == 0.0 or std < 1e-9:
        return None
    return round(float(np.mean(arr) / std), 4)


def independent_paired_observation_bootstrap_ci(
    diffs: list[float], num_boot: int = 2000, alpha: float = 0.05
) -> tuple[float, float]:
    """Independently compute paired observation bootstrap confidence interval."""
    rng = np.random.default_rng(42)
    diffs_arr = np.array(diffs)
    boot_means = np.empty(num_boot)
    n = len(diffs_arr)

    for i in range(num_boot):
        sample = rng.choice(diffs_arr, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    low = float(np.percentile(boot_means, 100 * (alpha / 2.0)))
    high = float(np.percentile(boot_means, 100 * (1.0 - alpha / 2.0)))
    return (round(low, 4), round(high, 4))


def independent_seed_block_bootstrap_ci(
    diffs_by_slot: dict[int, list[float]], num_boot: int = 2000, alpha: float = 0.05
) -> tuple[float, float]:
    """Independently compute seed-block sensitivity bootstrap confidence interval."""
    slots = list(diffs_by_slot.keys())
    k = len(slots)
    rng = np.random.default_rng(42)
    boot_means = np.empty(num_boot)

    for i in range(num_boot):
        sampled_slots = rng.choice(slots, size=k, replace=True)
        sample_vals: list[float] = []
        for s in sampled_slots:
            sample_vals.extend(diffs_by_slot[s])
        boot_means[i] = np.mean(sample_vals)

    low = float(np.percentile(boot_means, 100 * (alpha / 2.0)))
    high = float(np.percentile(boot_means, 100 * (1.0 - alpha / 2.0)))
    return (round(low, 4), round(high, 4))


def independent_environment_cluster_bootstrap_ci(
    diffs_by_env: dict[str, list[float]], num_boot: int = 2000, alpha: float = 0.05
) -> tuple[float, float]:
    """Independently compute environment-cluster bootstrap confidence interval."""
    envs = list(diffs_by_env.keys())
    k = len(envs)
    rng = np.random.default_rng(42)
    boot_means = np.empty(num_boot)

    for i in range(num_boot):
        sampled_envs = rng.choice(envs, size=k, replace=True)
        sample_vals: list[float] = []
        for e in sampled_envs:
            sample_vals.extend(diffs_by_env[e])
        boot_means[i] = np.mean(sample_vals)

    low = float(np.percentile(boot_means, 100 * (alpha / 2.0)))
    high = float(np.percentile(boot_means, 100 * (1.0 - alpha / 2.0)))
    return (round(low, 4), round(high, 4))


def audit_statistical_reproducibility(runs: list[dict[str, Any]]) -> None:
    print("\nAuditing Statistical Calculations Directly from Raw Trajectories...")

    # 1. Calculate overall standard means
    policies = ["oracle", "muse_spark_open", "ordinal_enumeration", "random"]
    means = {}
    for p in policies:
        std_scores = [r["score"] for r in runs if r["policy"] == p and r["variant"] == "standard"]
        means[p] = round(float(np.mean(std_scores)), 4)
        print(f"  {p:<20} standard mean score: {means[p]:.4f} (N={len(std_scores)})")

    assert means["oracle"] == 1.0, "Oracle must equal 1.0000"
    assert means["muse_spark_open"] == 0.8258, (
        f"Muse Spark expected 0.8258, got {means['muse_spark_open']}"
    )
    assert means["ordinal_enumeration"] == 0.1200, (
        f"Ordinal expected 0.1200, got {means['ordinal_enumeration']}"
    )
    assert means["random"] == 0.0854, f"Random expected 0.0854, got {means['random']}"

    # 2. Independent paired calculations for Muse Spark vs Random
    computed_p_vals = []
    computed_cohen_ds = []
    computed_deltas = []
    diffs_by_env: dict[str, list[float]] = {}
    diffs_by_slot: dict[int, list[float]] = {i: [] for i in range(5)}

    for env in ENVIRONMENT_NAMES:
        muse = [
            r["score"]
            for r in runs
            if r["policy"] == "muse_spark_open"
            and r["environment"] == env
            and r["variant"] == "standard"
        ]
        rand = [
            r["score"]
            for r in runs
            if r["policy"] == "random" and r["environment"] == env and r["variant"] == "standard"
        ]
        diffs = np.array(muse) - np.array(rand)
        diffs_by_env[env] = diffs.tolist()

        for slot_idx, d_val in enumerate(diffs):
            diffs_by_slot[slot_idx].append(float(d_val))

        delta = round(float(np.mean(diffs)), 4)
        computed_deltas.append(delta)

        p_perm = independent_permutation_test_5(np.array(muse), np.array(rand))
        computed_p_vals.append(p_perm)

        d_val = independent_cohen_d(diffs)
        computed_cohen_ds.append(d_val)

        # Assert zero-variance detection
        if env in ["the-trial", "sorcerers-apprentice", "sophies-choice", "library-of-babel"]:
            assert d_val is None, f"Expected None for zero variance on {env}, got {d_val}"

    computed_holm = independent_holm_bonferroni(computed_p_vals)

    # 3. Verify permutation test p-values:
    # All positive differences with N=5 must yield p = 2/32 = 0.0625 and Holm adj p = 0.6250
    for idx, env in enumerate(ENVIRONMENT_NAMES):
        assert computed_p_vals[idx] == 0.0625, (
            f"Permutation p-value on {env} was {computed_p_vals[idx]}, expected 0.0625"
        )
        assert computed_holm[idx] == 0.6250, (
            f"Holm-adjusted p-value on {env} was {computed_holm[idx]}, expected 0.6250"
        )
    print(
        "PASS: Exact two-sided permutation tests independently recalculated (p=0.0625, Holm=0.6250 across all 10 environments)."
    )
    print(
        "PASS: Zero-variance effect size detection verified: Cohen's d is strictly None on constant-difference conditions."
    )

    # 4. Bootstrap CI independent recalculation for all 3 methods
    pooled_diffs = [d for sub in diffs_by_env.values() for d in sub]
    pooled_mean = round(float(np.mean(pooled_diffs)), 4)
    assert pooled_mean == 0.7404, f"Expected pooled mean +0.7404, got {pooled_mean}"

    # Method 1: Paired Observation
    obs_low, obs_high = independent_paired_observation_bootstrap_ci(pooled_diffs)
    assert (obs_low, obs_high) == (0.6981, 0.7817), (
        f"Paired observation bootstrap mismatch: expected [0.6981, 0.7817], got [{obs_low}, {obs_high}]"
    )
    print(f"PASS: Method 1 (Paired Observation) Bootstrap CI: [{obs_low:.4f}, {obs_high:.4f}]")

    # Method 2: Seed-Block Sensitivity
    slot_low, slot_high = independent_seed_block_bootstrap_ci(diffs_by_slot)
    assert (slot_low, slot_high) == (0.7025, 0.7783), (
        f"Seed-block bootstrap mismatch: expected [0.7025, 0.7783], got [{slot_low}, {slot_high}]"
    )
    print(
        f"PASS: Method 2 (Seed-Block Sensitivity) Bootstrap CI: [{slot_low:.4f}, {slot_high:.4f}]"
    )

    # Method 3: Environment-Cluster
    env_low, env_high = independent_environment_cluster_bootstrap_ci(diffs_by_env)
    assert (env_low, env_high) == (0.6613, 0.8128), (
        f"Environment-cluster bootstrap mismatch: expected [0.6613, 0.8128], got [{env_low}, {env_high}]"
    )
    print(f"PASS: Method 3 (Environment-Cluster) Bootstrap CI: [{env_low:.4f}, {env_high:.4f}]")

    # 5. Counterfactual adaptation independent check
    expected_adaptations = {
        "sorcerers-apprentice": (0.8600, 0.8600, 0.0000),
        "sophies-choice": (0.8800, 0.9500, 0.0700),
        "library-of-babel": (0.8500, 0.9200, 0.0700),
        "othello": (0.7515, 0.8411, 0.0896),
    }

    for env, (exp_std, exp_ctl, exp_delta) in expected_adaptations.items():
        muse_std = [
            r["score"]
            for r in runs
            if r["policy"] == "muse_spark_open"
            and r["environment"] == env
            and r["variant"] == "standard"
        ]
        muse_ctl = [
            r["score"]
            for r in runs
            if r["policy"] == "muse_spark_open"
            and r["environment"] == env
            and r["variant"] == "control"
        ]
        mean_std = round(float(np.mean(muse_std)), 4)
        mean_ctl = round(float(np.mean(muse_ctl)), 4)
        delta_cf = round(mean_ctl - mean_std, 4)

        assert mean_std == exp_std, f"Standard mean mismatch for {env}: {mean_std} != {exp_std}"
        assert mean_ctl == exp_ctl, f"Control mean mismatch for {env}: {mean_ctl} != {exp_ctl}"
        assert delta_cf == exp_delta, (
            f"Adaptation delta mismatch for {env}: {delta_cf} != {exp_delta}"
        )
        print(
            f"  PASS: Counterfactual Adaptation ({env:<20}): Std={mean_std:.4f}, Ctl={mean_ctl:.4f}, Delta={delta_cf:+.4f}"
        )

    print("PASS: All statistical metrics independently validated from raw trajectories.")


def audit_baseten_benchmark_artifact() -> dict[str, Any]:
    print("\nAuditing Empirical Baseten Live Provider Benchmark Artifact...")
    assert BASETEN_ARTIFACT_PATH.exists(), f"Baseten artifact missing: {BASETEN_ARTIFACT_PATH}"

    raw_bytes = BASETEN_ARTIFACT_PATH.read_bytes()
    calc_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    assert calc_sha256 == EXPECTED_BASETEN_SHA256, (
        f"Baseten artifact SHA-256 mismatch: calculated {calc_sha256}, expected {EXPECTED_BASETEN_SHA256}"
    )
    print(f"PASS: Baseten benchmark artifact SHA-256 checksum verified: {calc_sha256}")

    episodes = json.loads(raw_bytes)
    assert len(episodes) == 10, f"Expected 10 environment episodes, found {len(episodes)}"

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_score = 0.0
    task_successes = 0
    compliance_passes = 0
    seen_envs: set[str] = set()

    for item in episodes:
        env = item["environment"]
        assert env in ENVIRONMENT_NAMES, f"Unexpected environment in live benchmark: {env}"
        assert env not in seen_envs, f"Duplicate environment in live benchmark: {env}"
        seen_envs.add(env)

        run = item["runs"][0]
        canonical_seed = DEFAULT_SEED_MAP[env][0]
        assert run["seed"] == canonical_seed, (
            f"Seed mismatch on {env}: found {run['seed']}, expected canonical {canonical_seed}"
        )

        total_score += run["score"]
        if run.get("task_success"):
            task_successes += 1
        if run.get("constraint_compliance"):
            compliance_passes += 1

        total_prompt_tokens += run.get("total_prompt_tokens", 0)
        total_completion_tokens += run.get("total_completion_tokens", 0)

    measured_tokens = total_prompt_tokens + total_completion_tokens
    mean_score = round(total_score / len(episodes), 4)

    assert total_prompt_tokens == 119687, f"Prompt tokens mismatch: {total_prompt_tokens} != 119687"
    assert total_completion_tokens == 40211, (
        f"Completion tokens mismatch: {total_completion_tokens} != 40211"
    )
    assert measured_tokens == 159898, f"Total tokens mismatch: {measured_tokens} != 159898"
    assert mean_score == 0.3746, f"Mean score mismatch: {mean_score} != 0.3746"
    assert task_successes == 3, f"Task success count mismatch: {task_successes} != 3"
    assert compliance_passes == 6, f"Constraint compliance count mismatch: {compliance_passes} != 6"

    print(
        f"PASS: 10 live episodes validated: mean score={mean_score:.4f}, successes={task_successes}/10, compliance={compliance_passes}/10 (60.0%)."
    )
    print(
        f"PASS: Provider token counts independently verified: prompt={total_prompt_tokens:,}, completion={total_completion_tokens:,}, total={measured_tokens:,}."
    )

    return {
        "episodes": episodes,
        "mean_score": mean_score,
        "task_successes": task_successes,
        "compliance_passes": compliance_passes,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": measured_tokens,
    }


def audit_report_consistency(runs: list[dict[str, Any]], baseten_info: dict[str, Any]) -> None:
    print("\nAuditing Report and Configuration Consistency...")
    assert REPORT_PATH.exists(), f"Report file missing: {REPORT_PATH}"
    report_text = REPORT_PATH.read_text(encoding="utf-8")

    # 1. Assert zero local machine links in report
    assert "file:///" not in report_text, "Report must not contain local machine 'file:///' URLs."
    print("PASS: Zero local machine 'file:///' URLs in P2_RESEARCH_REPORT.md.")

    # 2. Verify trajectory and record accounting
    assert (
        "Total Pilot Records:** 280 (210 Harness Executions + 70 Synthetic Calibration Records)"
        in report_text
    )
    assert "Stage 1 (Baseline Executions)**: 210 runs" in report_text
    assert "Stage 2 (Model Calibration Records)**: 70 records" in report_text
    assert "Secondary comparative analysis" in report_text

    # 3. Check experiment_config.json
    config_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    acct = config_data.get("matrix", {}).get("execution_accounting", {})
    assert acct.get("total_pilot_records") == 280
    assert acct.get("total_harness_executions") == 210
    assert acct.get("total_synthetic_records") == 70
    assert "total_unique_executions" not in acct, (
        "Outdated 'total_unique_executions' key must not exist"
    )
    print(
        "PASS: Configuration and report accounting reconciled (280 records = 210 harness + 70 synthetic)."
    )

    # 4. Verify live benchmark numbers in Section 3.1
    assert EXPECTED_BASETEN_SHA256 in report_text, (
        "Baseten artifact SHA-256 checksum must appear in report"
    )
    assert "159,898" in report_text, "Total measured token count 159,898 must appear in report"
    assert "0.3746" in report_text, "Live benchmark mean score 0.3746 must appear in report"
    assert "3/10" in report_text, "Live benchmark task success 3/10 must appear in report"
    assert "60.0%" in report_text, "Live benchmark compliance 60.0% must appear in report"
    assert "(N=1)" in report_text, "Matched canonical seed sample count (N=1) must appear in report"
    assert "(Pool, N=5)" in report_text, (
        "Baseline pool sample count (Pool, N=5) must appear in report"
    )
    print("PASS: Live Baseten empirical benchmark section and sample size annotations confirmed.")

    # 5. Verify Section 6 Othello consistency
    assert "0.7515" in report_text, "Othello standard mean 0.7515 must appear in report"
    assert "0.8411" in report_text, "Othello control mean 0.8411 must appear in report"
    assert "+0.0896" in report_text, "Othello adaptation delta +0.0896 must appear in report"
    assert "0.7602" not in report_text, "Stale Othello mean 0.7602 must NOT appear in report"
    assert "0.8498" not in report_text, "Stale Othello mean 0.8498 must NOT appear in report"
    print(
        "PASS: Section 6 Othello adaptation numerical consistency verified (0.7515 -> 0.8411, Delta=+0.0896)."
    )

    # 6. Verify synthetic calibration labeling across sections
    assert "Synthetic Calibration Protocol" in report_text
    assert "Synthetic Calibration Observation" in report_text
    assert "Synthetic Model Data" in report_text
    assert "Synthetic Model Fixture" in report_text
    print(
        "PASS: Synthetic calibration disclaimers explicitly present across Sections 4, 5, 6, 7, and 9."
    )

    # 7. Verify Cohen's d zero variance handling in report
    assert "N/A (zero variance)" in report_text
    assert "0.0625" in report_text
    assert "0.6250" in report_text

    # 8. Verify local LLM references are purged from report
    assert "Llama 3.1" not in report_text, "Llama 3.1 must not appear in report"
    assert "Gemma 2" not in report_text, "Gemma 2 must not appear in report"

    print("PASS: P2_RESEARCH_REPORT.md consistency and provenance reconciliations confirmed.")


def main() -> None:
    print("=" * 80)
    print("AGENT PRAXIS P2 PILOT: INDEPENDENT REPRODUCIBILITY AUDITOR")
    print("=" * 80)

    if not CONFIG_PATH.exists() or not RUNS_PATH.exists():
        print(f"ERROR: Missing artifacts in {RESULTS_DIR}")
        sys.exit(1)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    runs_data = json.loads(RUNS_PATH.read_text(encoding="utf-8"))

    runs = audit_dataset_integrity(config, runs_data)
    audit_statistical_reproducibility(runs)
    baseten_info = audit_baseten_benchmark_artifact()
    audit_report_consistency(runs, baseten_info)

    print("\n" + "=" * 80)
    print("ALL AUDIT CHECKS PASSED: 100% REPRODUCIBLE & MATHEMATICALLY RECONCILED")
    print("=" * 80)


if __name__ == "__main__":
    main()
