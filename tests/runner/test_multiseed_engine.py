"""Unit and integration test suite for the Multi-Seed Execution & Statistical Engine."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from starlette.testclient import TestClient

from agent_praxis.framework.runner.multiseed.checkpoint import CheckpointManager
from agent_praxis.framework.runner.multiseed.executor import MultiSeedExecutor
from agent_praxis.framework.runner.multiseed.limiter import (
    AsyncTokenBucket,
)
from agent_praxis.framework.runner.multiseed.matrix import expand_workload_matrix
from agent_praxis.framework.runner.multiseed.schemas import (
    DEFAULT_SEED_MAP,
    BenchmarkRunManifest,
    EpisodeResult,
    EpisodeSpec,
    EpisodeStatus,
    ExecutionTier,
    SeedConfig,
    SeedStrategy,
)
from agent_praxis.framework.runner.multiseed.seeds import (
    get_tier_seed_config,
)
from agent_praxis.framework.runner.multiseed.stats import (
    compute_continuous_score_ci,
    compute_decision_consistency,
    compute_trajectory_jaccard_consistency,
    compute_wilson_score_interval,
)
from agent_praxis.server import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --------------------------------------------------------------------------- #
# 1. Seed Resolution & Configuration Tests
# --------------------------------------------------------------------------- #


def test_canonical_seed_resolution_matches_default_map():
    cfg = SeedConfig(strategy=SeedStrategy.CANONICAL, num_seeds=5)
    for env_name, expected_seeds in DEFAULT_SEED_MAP.items():
        assert cfg.resolve_seeds(env_name) == expected_seeds


def test_canonical_seed_extension_for_large_n():
    cfg = SeedConfig(strategy=SeedStrategy.CANONICAL, num_seeds=8)
    seeds = cfg.resolve_seeds("dorian-gray")
    assert len(seeds) == 8
    # First 5 must strictly match canonical
    assert seeds[:5] == DEFAULT_SEED_MAP["dorian-gray"]
    # Remaining 3 must be deterministic integers > 0
    assert all(isinstance(s, int) and s > 0 for s in seeds)
    # Rerunning resolution yields identical seeds
    assert cfg.resolve_seeds("dorian-gray") == seeds


def test_explicit_and_sequential_seed_resolution():
    cfg_explicit = SeedConfig(strategy=SeedStrategy.EXPLICIT, explicit_seeds=[42, 43, 44])
    assert cfg_explicit.resolve_seeds("any-env") == [42, 43, 44]

    cfg_seq = SeedConfig(strategy=SeedStrategy.SEQUENTIAL, base_seed=1000, num_seeds=4)
    assert cfg_seq.resolve_seeds("any-env") == [1000, 1001, 1002, 1003]


def test_tier_defaults_configuration():
    ci_cfg = get_tier_seed_config(ExecutionTier.CI)
    assert ci_cfg.num_seeds == 1

    smoke_cfg = get_tier_seed_config(ExecutionTier.SMOKE)
    assert smoke_cfg.num_seeds == 3

    full_cfg = get_tier_seed_config(ExecutionTier.FULL)
    assert full_cfg.num_seeds == 5

    robustness_cfg = get_tier_seed_config(ExecutionTier.ROBUSTNESS)
    assert robustness_cfg.num_seeds == 20

    rand_cfg = get_tier_seed_config(ExecutionTier.RANDOM_CEILING)
    assert rand_cfg.num_seeds == 40
    assert rand_cfg.strategy == SeedStrategy.SEQUENTIAL


# --------------------------------------------------------------------------- #
# 2. Matrix Expansion & Idempotency Key Tests
# --------------------------------------------------------------------------- #


def test_matrix_expansion_unique_idempotency_keys():
    models = [("llama3.1:8b", "ollama"), ("gpt-4o", "openai")]
    envs = ["dorian-gray", "1984"]
    variants = ["standard", "control"]
    cfg = SeedConfig(strategy=SeedStrategy.CANONICAL, num_seeds=3)

    specs = expand_workload_matrix(models, envs, variants, cfg)
    # Expected total: 2 models * 2 envs * 2 variants * 3 seeds = 24 specs
    assert len(specs) == 24

    keys = [spec.idempotency_key for spec in specs]
    # Every episode spec must have a unique, deterministic SHA-256 idempotency key
    assert len(set(keys)) == 24
    assert all(len(k) == 64 for k in keys)


# --------------------------------------------------------------------------- #
# 3. Statistical Formulations Tests (Wilson, Student-t, Consistency)
# --------------------------------------------------------------------------- #


def test_wilson_interval_boundary_conditions():
    # 0 successes out of 5: Wilson lower bound is 0.0, upper bound > 0.0 (reflects epistemic uncertainty)
    ci_zero = compute_wilson_score_interval(successes=0, total=5)
    assert ci_zero.lower == 0.0
    assert 0.35 <= ci_zero.upper <= 0.50

    # 5 successes out of 5: Wilson upper bound is 1.0, lower bound < 1.0
    ci_all = compute_wilson_score_interval(successes=5, total=5)
    assert 0.50 <= ci_all.lower <= 0.65
    assert ci_all.upper == 1.0

    # Degenerate total=0
    ci_deg = compute_wilson_score_interval(successes=0, total=0)
    assert ci_deg.lower == 0.0 and ci_deg.upper == 0.0


def test_continuous_score_ci_bounds():
    scores = [0.85, 0.90, 0.95, 0.88, 0.92]
    ci = compute_continuous_score_ci(scores)
    assert ci.method == "student_t"
    assert 0.80 <= ci.lower <= 0.88
    assert 0.92 <= ci.upper <= 1.0


def test_consistency_metrics():
    # Helper to construct dummy episode results
    def make_dummy_ep(
        task_succ: bool, trap: bool, term_act: str, actions: list[str]
    ) -> EpisodeResult:
        spec = EpisodeSpec(
            provider="mock",
            model_id="test-model",
            environment_name="dorian-gray",
            variant="standard",
            seed=101,
        )
        from datetime import UTC, datetime

        return EpisodeResult(
            idempotency_key=spec.idempotency_key,
            spec=spec,
            status=EpisodeStatus.COMPLETED,
            task_success=task_succ,
            trap_triggered=trap,
            terminal_action=term_act,
            action_sequence=actions,
            started_at_utc=datetime.now(UTC),
            completed_at_utc=datetime.now(UTC),
        )

    ep1 = make_dummy_ep(True, False, "finalize", ["read_status", "read_logs", "finalize"])
    ep2 = make_dummy_ep(True, False, "finalize", ["read_status", "read_logs", "finalize"])
    ep3 = make_dummy_ep(False, True, "patch_health_report", ["read_status", "patch_health_report"])

    episodes = [ep1, ep2, ep3]
    # Decision consistency: modal outcome is (True, False, finalize) occurring 2 out of 3 = 0.6667
    assert 0.66 <= compute_decision_consistency(episodes) <= 0.67
    # Trajectory consistency > 0
    assert 0.0 < compute_trajectory_jaccard_consistency(episodes) <= 1.0


# --------------------------------------------------------------------------- #
# 4. Checkpoint WAL and Crash Recovery Tests
# --------------------------------------------------------------------------- #


def test_checkpoint_manager_crash_recovery(tmp_path: Path):
    wal_file = tmp_path / "test_run.wal.jsonl"
    mgr = CheckpointManager(wal_file)

    spec = EpisodeSpec(
        provider="mock",
        model_id="m1",
        environment_name="dorian-gray",
        variant="standard",
        seed=20260201,
    )
    from datetime import UTC, datetime

    ep1 = EpisodeResult(
        idempotency_key=spec.idempotency_key,
        spec=spec,
        status=EpisodeStatus.COMPLETED,
        raw_score=1.0,
        task_success=True,
        started_at_utc=datetime.now(UTC),
        completed_at_utc=datetime.now(UTC),
    )

    asyncio.run(mgr.append_result(ep1))
    assert wal_file.exists()

    # Simulate a crash that leaves a truncated partial JSON line at the end
    with wal_file.open("a", encoding="utf-8") as f:
        f.write('{"idempotency_key": "broken-incomplete-li\n')

    # Manager must safely recover the valid record and ignore the truncated tail
    completed = mgr.load_completed_results()
    assert len(completed) == 1
    assert spec.idempotency_key in completed

    # filter_pending_specs must detect spec as already completed
    pending, done = mgr.filter_pending_specs([spec])
    assert len(pending) == 0
    assert len(done) == 1


# --------------------------------------------------------------------------- #
# 5. Dual Token-Bucket Rate Limiter Tests
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_async_token_bucket_acquisition_and_cooldown():
    bucket = AsyncTokenBucket(capacity=5.0, refill_rate_per_sec=10.0)
    await bucket.acquire(2.0)
    assert bucket.tokens <= 3.5

    # Test 429 Retry-After cooldown
    await bucket.apply_retry_after(0.05)
    import time

    start = time.monotonic()
    await bucket.acquire(1.0)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.04


# --------------------------------------------------------------------------- #
# 6. Evaluator Server DELETE /api/session Route Test
# --------------------------------------------------------------------------- #


def test_server_delete_session_endpoint():
    client = TestClient(app)
    setup_resp = client.post(
        "/api/setup",
        json={"environment_name": "dorian-gray", "seed": 20260201, "variant": "standard"},
    )
    assert setup_resp.status_code == 200
    sid = setup_resp.json()["session_id"]

    # Delete session explicitly
    del_resp = client.delete(f"/api/session/{sid}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "dropped"

    # Second delete returns not_found
    del_resp2 = client.delete(f"/api/session/{sid}")
    assert del_resp2.status_code == 200
    assert del_resp2.json()["status"] == "not_found"


# --------------------------------------------------------------------------- #
# 7. End-to-End Multi-Seed Execution Test
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_multi_seed_executor_end_to_end(tmp_path: Path):
    wal_file = tmp_path / "e2e.wal.jsonl"
    report_file = tmp_path / "e2e_report.json"
    mgr = CheckpointManager(wal_file)

    models = [("mock-model", "mock")]
    envs = ["dorian-gray", "the-trial"]
    variants = ["standard", "control"]
    cfg = SeedConfig(strategy=SeedStrategy.CANONICAL, num_seeds=2)

    specs = expand_workload_matrix(models, envs, variants, cfg)
    assert len(specs) == 8  # 1 model * 2 envs * 2 variants * 2 seeds = 8

    executor = MultiSeedExecutor(mgr, concurrency=4)
    results = await executor.run_suite(specs)
    assert len(results) == 8
    assert all(r.status == EpisodeStatus.COMPLETED for r in results)

    # Compile final canonical report
    manifest = BenchmarkRunManifest(
        run_id="test-e2e-run",
        execution_tier=ExecutionTier.SMOKE,
        seed_config=cfg,
        started_at_utc=results[0].started_at_utc,
    )
    report = mgr.compile_final_report(manifest, report_file)
    assert report_file.exists()
    assert (
        len(report.aggregates) == 4
    )  # (dorian-gray, standard), (dorian-gray, control), (the-trial, standard), (the-trial, control)

    # Verify control variant trap fall rate is None per LLM 2 / LLM 3 rule
    for agg in report.aggregates:
        if agg.variant == "control":
            assert agg.trap_fall_rate is None
            assert agg.trap_fall_wilson_ci is None
        elif agg.variant == "standard":
            assert agg.trap_fall_rate is not None
