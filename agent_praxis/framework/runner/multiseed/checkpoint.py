"""Resilient Write-Ahead Log (.wal.jsonl) and atomic report compiler."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

from agent_praxis.framework.runner.multiseed.schemas import (
    BenchmarkRunManifest,
    BenchmarkSuiteReport,
    EpisodeResult,
    EpisodeSpec,
    EpisodeStatus,
)
from agent_praxis.framework.runner.multiseed.stats import (
    aggregate_suite_results,
    compute_adversarial_deltas,
)


class CheckpointManager:
    """Coroutine-safe append-only JSONL WAL with crash-tolerant deduplication."""

    def __init__(self, wal_path: Path) -> None:
        self.wal_path = Path(wal_path)
        self._write_lock = asyncio.Lock()
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)

    def load_completed_results(self) -> dict[str, EpisodeResult]:
        """Scan the WAL on startup.

        Tolerates partial or truncated trailing lines from sudden process termination.
        Returns only COMPLETED records keyed by idempotency_key.
        """
        completed: dict[str, EpisodeResult] = {}
        if not self.wal_path.exists():
            return completed

        with self.wal_path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = EpisodeResult.model_validate_json(line)
                    if record.status == EpisodeStatus.COMPLETED:
                        completed[record.idempotency_key] = record
                except Exception:
                    # Ignore truncated or corrupted trailing lines
                    continue
        return completed

    def filter_pending_specs(
        self, all_specs: Iterable[EpisodeSpec]
    ) -> tuple[list[EpisodeSpec], list[EpisodeResult]]:
        """Partition expanded matrix into (pending_specs_to_run, completed_results)."""
        completed_map = self.load_completed_results()
        pending: list[EpisodeSpec] = []
        for spec in all_specs:
            if spec.idempotency_key not in completed_map:
                pending.append(spec)
        return pending, list(completed_map.values())

    async def append_result(self, result: EpisodeResult) -> None:
        """Atomically append a serialized result and flush OS buffers."""
        serialized = result.model_dump_json() + "\n"
        async with self._write_lock:
            with self.wal_path.open("a", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())

    def compile_final_report(
        self,
        manifest: BenchmarkRunManifest,
        output_json_path: Path,
    ) -> BenchmarkSuiteReport:
        """Compile all completed results from the WAL into an atomic canonical JSON report."""
        completed_map = self.load_completed_results()
        episodes = list(completed_map.values())
        aggregates = aggregate_suite_results(episodes)
        deltas = compute_adversarial_deltas(aggregates)

        report = BenchmarkSuiteReport(
            manifest=manifest,
            aggregates=aggregates,
            adversarial_deltas=deltas,
        )

        output_path = Path(output_json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, output_path)
        return report
