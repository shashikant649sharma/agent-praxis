"""Regression tests for tools/verify_results_provenance.py validator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from tools.verify_results_provenance import check_document


def _create_minimal_run_record(
    repo_commit: str,
    bench_sha: str,
    wrap_sha: str,
    provenance_notes: str | None = None,
) -> dict[str, Any]:
    harness: dict[str, Any] = {
        "benchmark_models_sha256": bench_sha,
        "gymnasium_wrapper_sha256": wrap_sha,
    }
    if provenance_notes is not None:
        harness["provenance_notes"] = provenance_notes

    return {
        "model": "test-model",
        "environment": "dorian-gray",
        "seed": 1,
        "variant": "standard",
        "score": 1.0,
        "task_success": True,
        "constraint_compliance": True,
        "path": ["step_1"],
        "raw_responses": [{"action_index": 0}],
        "parse_failures": 0,
        "provenance": {
            "repo_commit": repo_commit,
            "model": "test-model",
            "provider": "test-provider",
            "environment": "dorian-gray",
            "seed": 1,
            "variant": "standard",
            "prompt_version": "sre-json-action-index-v1",
            "system_prompt_sha256": "5122b4fc6cb2d30f9cdadaa51f4aef3ac3b6bce8723c602f49ca24a28509fb3d",
            "decoding": {"temperature": 0.0},
            "started_at": "2026-10-30T10:00:00Z",
            "finished_at": "2026-10-30T10:01:00Z",
            "harness_source_hashes": harness,
        },
    }


def test_dirty_commit_fails_closed_without_provenance_notes(tmp_path: Path) -> None:
    doc = [
        _create_minimal_run_record(
            "73df97a67873181c93b955f6270de10c60998e95-dirty", "a" * 64, "b" * 64
        )
    ]
    p = tmp_path / "test.json"
    p.write_text(json.dumps(doc), encoding="utf-8")

    problems = check_document(p, require_harness_hashes=True)
    assert any(
        "repo_commit is marked -dirty but harness_source_hashes lacks 'provenance_notes'" in pr
        for pr in problems
    )


def test_dirty_commit_fails_closed_with_unverifiable_commits(tmp_path: Path) -> None:
    doc = [
        _create_minimal_run_record(
            "73df97a67873181c93b955f6270de10c60998e95-dirty",
            "a" * 64,
            "b" * 64,
            provenance_notes="Bogus commit reference deadbeefcafe1234567890",
        )
    ]
    p = tmp_path / "test.json"
    p.write_text(json.dumps(doc), encoding="utf-8")

    problems = check_document(p, require_harness_hashes=True)
    assert any("contains no verifiable git reconciling commits" in pr for pr in problems)


def test_dirty_commit_fails_when_hashes_do_not_match_reconciling_commit(tmp_path: Path) -> None:
    # be6c6d4ac5042 is a valid commit in the repository, but dummy hashes don't match it
    doc = [
        _create_minimal_run_record(
            "73df97a67873181c93b955f6270de10c60998e95-dirty",
            "1111111111111111111111111111111111111111111111111111111111111111",
            "2222222222222222222222222222222222222222222222222222222222222222",
            provenance_notes="Updates committed in be6c6d4ac5042.",
        )
    ]
    p = tmp_path / "test.json"
    p.write_text(json.dumps(doc), encoding="utf-8")

    problems = check_document(p, require_harness_hashes=True)
    assert any(
        "dirty tree hashes match no single valid reconciling commit" in pr for pr in problems
    )


def test_dirty_commit_succeeds_when_both_hashes_match_same_reconciling_commit(
    tmp_path: Path,
) -> None:
    # Exact hashes from be6c6d4ac5042
    doc = [
        _create_minimal_run_record(
            "73df97a67873181c93b955f6270de10c60998e95-dirty",
            "7f6ed3be05df7b837737eb0e895b9a85f02bae0b2c80f1712db15202d3c56917",
            "f0c03cd916aedb63939ddabfc00f7e1cf74b3b276d184cc48aadf1d736380e12",
            provenance_notes="Baseten inference and runner updates committed in be6c6d4ac5042.",
        )
    ]
    p = tmp_path / "test.json"
    p.write_text(json.dumps(doc), encoding="utf-8")

    problems = check_document(p, require_harness_hashes=True)
    assert problems == []


def test_clean_commit_fails_on_wrapper_mismatch(tmp_path: Path) -> None:
    # Using commit be6c6d4 with valid runner hash but incorrect wrapper hash
    doc = [
        _create_minimal_run_record(
            "be6c6d4ac5042f206e5892f5113074cf0a6db3d9",
            "7f6ed3be05df7b837737eb0e895b9a85f02bae0b2c80f1712db15202d3c56917",
            "0000000000000000000000000000000000000000000000000000000000000000",
        )
    ]
    p = tmp_path / "test.json"
    p.write_text(json.dumps(doc), encoding="utf-8")

    problems = check_document(p, require_harness_hashes=True)
    assert any(
        "recorded gymnasium_wrapper_sha256" in pr and "does not match commit" in pr
        for pr in problems
    )
