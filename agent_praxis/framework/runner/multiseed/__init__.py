"""Agent Praxis Multi-Seed Benchmarking & Evaluation Engine.

Provides matrix expansion, provider-aware rate limiting, resilient WAL checkpointing,
and small-sample statistical estimation (Wilson CIs, bootstrap, consistency).
"""

from __future__ import annotations

from agent_praxis.framework.runner.multiseed.schemas import (
    DEFAULT_SEED_MAP,
    BenchmarkRunManifest,
    BenchmarkSuiteReport,
    ConfidenceInterval,
    DecodingParameters,
    EpisodeResult,
    EpisodeSpec,
    EpisodeStatus,
    ExecutionTier,
    MatchedSeedDelta,
    ModelComparisonReport,
    MultiSeedAggregateResult,
    OperationalReliabilitySummary,
    PrimaryFailureBreakdown,
    PrimaryFailureReason,
    SeedConfig,
    SeedSplit,
    SeedStrategy,
    TrapRateSummary,
    classify_primary_failure,
    validate_episode_record,
)

__all__ = [
    "DEFAULT_SEED_MAP",
    "BenchmarkRunManifest",
    "BenchmarkSuiteReport",
    "ConfidenceInterval",
    "DecodingParameters",
    "EpisodeResult",
    "EpisodeSpec",
    "EpisodeStatus",
    "ExecutionTier",
    "MatchedSeedDelta",
    "ModelComparisonReport",
    "MultiSeedAggregateResult",
    "OperationalReliabilitySummary",
    "PrimaryFailureBreakdown",
    "PrimaryFailureReason",
    "SeedConfig",
    "SeedSplit",
    "SeedStrategy",
    "TrapRateSummary",
    "classify_primary_failure",
    "validate_episode_record",
]
