"""Canonical data contracts for multi-seed execution and statistical aggregation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

# --------------------------------------------------------------------------- #
# 1. Seed Configuration & Strategies
# --------------------------------------------------------------------------- #


class SeedStrategy(StrEnum):
    CANONICAL = "canonical"  # Slices from DEFAULT_SEED_MAP; extends with SHA-256 for N > 5
    EXPLICIT = "explicit"  # Uses exact user-supplied seed list
    SEQUENTIAL = "sequential"  # [base_seed + i for i in range(num_seeds)]
    DETERMINISTIC_PRNG = "prng"  # HMAC/SHA-256 derived seeds from (base_seed, env, index)


class ExecutionTier(StrEnum):
    CI = "ci"  # 1 seed, standard variant only (<25s fast gate)
    SMOKE = "smoke"  # 3 seeds, standard + control
    FULL = "full"  # 5 canonical seeds, standard + control (100 episodes/model)
    ROBUSTNESS = "robustness"  # 20 seeds, standard + control (400 episodes/model)
    RANDOM_CEILING = "random_ceiling"  # 40 sequential seeds [1000..1039] for random baseline


DEFAULT_SEED_MAP: dict[str, list[int]] = {
    "dorian-gray": [20260201, 20260202, 20260203, 20260204, 20260205],
    "catch-22": [20260301, 20260302, 20260303, 20260304, 20260305],
    "1984": [20260501, 20260502, 20260503, 20260504, 20260505],
    "metamorphosis": [20260401, 20260402, 20260403, 20260404, 20260405],
    "the-trial": [20260601, 20260602, 20260603, 20260604, 20260605],
    "frankenstein": [18180101, 18180102, 18180103, 18180104, 18180105],
    "sorcerers-apprentice": [20261001, 20261002, 20261003, 20261004, 20261005],
    "sophies-choice": [20261026, 20261027, 20261028, 20261029, 20261030],
    "library-of-babel": [20261101, 20261102, 20261103, 20261104, 20261105],
    "othello": [20261115, 20261116, 20261117, 20261118, 20261119],
}


class SeedConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: SeedStrategy = SeedStrategy.CANONICAL
    num_seeds: int = Field(default=5, ge=1, le=1000)
    explicit_seeds: list[int] | None = None
    base_seed: int = Field(default=1000, description="Base offset for SEQUENTIAL / PRNG")

    def resolve_seeds(self, environment_name: str) -> list[int]:
        """Deterministically resolve the exact seed list for a given environment."""
        if self.strategy == SeedStrategy.EXPLICIT:
            if not self.explicit_seeds:
                raise ValueError("explicit_seeds must be non-empty when strategy='explicit'")
            return list(self.explicit_seeds)

        if self.strategy == SeedStrategy.SEQUENTIAL:
            return [self.base_seed + i for i in range(self.num_seeds)]

        if self.strategy == SeedStrategy.CANONICAL:
            canonical = DEFAULT_SEED_MAP.get(environment_name, [101, 102, 103, 104, 105])
            if self.num_seeds <= len(canonical):
                return canonical[: self.num_seeds]
            # Deterministically extend canonical seeds if num_seeds > 5
            extended = list(canonical)
            for idx in range(len(canonical), self.num_seeds):
                digest = hashlib.sha256(f"{environment_name}:canonical_ext:{idx}".encode()).digest()
                extended.append(int.from_bytes(digest[:4], "big") % 90_000_000 + 10_000_000)
            return extended

        if self.strategy == SeedStrategy.DETERMINISTIC_PRNG:
            seeds: list[int] = []
            for idx in range(self.num_seeds):
                digest = hashlib.sha256(
                    f"{self.base_seed}:{environment_name}:{idx}".encode()
                ).digest()
                seeds.append(int.from_bytes(digest[:4], "big") % 90_000_000 + 10_000_000)
            return seeds

        raise ValueError(f"Unsupported seed strategy: {self.strategy}")


# --------------------------------------------------------------------------- #
# 2. Decoding, Spec & Single-Episode Provenance Contracts
# --------------------------------------------------------------------------- #


class DecodingParameters(BaseModel):
    model_config = ConfigDict(frozen=True)

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=1)
    max_turns: int = Field(default=16, ge=1)
    context_policy: Literal["full_history", "sliding_window_4", "sliding_window_8"] = "full_history"
    prompt_version: str = "sre-json-action-index-v1"
    response_format: Literal["json_object", "text", "tool_call"] = "json_object"


class EpisodeSpec(BaseModel):
    """Immutable specification of a single benchmark episode job."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model_id: str
    environment_name: str
    variant: Literal["standard", "control"]
    seed: int
    decoding: DecodingParameters = Field(default_factory=DecodingParameters)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def idempotency_key(self) -> str:
        """Deterministic SHA-256 key used for WAL deduplication and resumption."""
        payload = {
            "provider": self.provider,
            "model_id": self.model_id,
            "environment_name": self.environment_name,
            "variant": self.variant,
            "seed": self.seed,
            "temperature": self.decoding.temperature,
            "max_turns": self.decoding.max_turns,
            "context_policy": self.decoding.context_policy,
            "prompt_version": self.decoding.prompt_version,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class TurnTraceSummary(BaseModel):
    turn_index: int
    action_name: str
    action_type: Literal["diagnostic", "mutation", "terminal", "invalid"] = "diagnostic"
    outcome_kind: Literal[
        "valid_action",
        "parse_failure",
        "invalid_action",
        "provider_error",
        "context_overflow",
    ] = "valid_action"
    action_index: int | None = None
    parse_error: bool = False
    evidence_gate_violation: bool = False
    trap_triggered: bool = False
    turn_latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_measured: bool = False
    truncation_status: str = "none"


class EpisodeStatus(StrEnum):
    COMPLETED = "completed"
    FAILED_TRANSIENT = "failed_transient"  # Network / 429 / 503 - eligible for retry
    FAILED_FATAL = "failed_fatal"  # Unrecoverable auth or configuration error


class EpisodeResult(BaseModel):
    """Complete provenance of a single seed execution."""

    idempotency_key: str
    spec: EpisodeSpec
    status: EpisodeStatus

    # Evaluation Outcomes
    raw_score: float = Field(default=0.0, ge=0.0, le=1.0)
    task_success: bool = False
    constraint_compliance: bool = True
    trap_triggered: bool = False
    trap_penalty: float = Field(default=0.0, ge=0.0)
    evidence_before_mutation_violated: bool = False
    evidence_penalty: float = Field(default=0.0, ge=0.0)

    # Behavioral & Parse Telemetry
    steps_taken: int = Field(default=0, ge=0)
    parse_failure_count: int = Field(default=0, ge=0)
    invalid_action_count: int = Field(default=0, ge=0)
    provider_error_count: int = Field(default=0, ge=0)
    context_overflow_count: int = Field(default=0, ge=0)
    action_sequence: list[str] = Field(default_factory=list)
    terminal_action: str | None = None
    turn_traces: list[TurnTraceSummary] = Field(default_factory=list)

    # Latency & Token Accounting
    total_latency_ms: float = Field(default=0.0, ge=0.0)
    evaluator_latency_ms: float = Field(default=0.0, ge=0.0)
    inference_latency_ms: float = Field(default=0.0, ge=0.0)
    total_prompt_tokens: int = Field(default=0, ge=0)
    total_completion_tokens: int = Field(default=0, ge=0)
    tokens_measured: bool = False
    truncation_provenance: dict[str, Any] = Field(default_factory=dict)

    # Diagnostics
    error_message: str | None = None
    started_at_utc: datetime
    completed_at_utc: datetime


# --------------------------------------------------------------------------- #
# 3. Statistical Aggregation Contracts
# --------------------------------------------------------------------------- #


class ConfidenceInterval(BaseModel):
    lower: float
    upper: float
    confidence_level: float = 0.95
    method: Literal["wilson", "student_t", "bootstrap_bca", "degenerate"] = "wilson"


class MultiSeedAggregateResult(BaseModel):
    """Statistical summary for a specific (model_id, environment_name, variant) tuple."""

    provider: str
    model_id: str
    environment_name: str
    variant: Literal["standard", "control"]

    # Sample Provenance
    sample_size_n: int = Field(ge=1)
    seeds_evaluated: list[int]
    failed_episodes_count: int = 0

    # Continuous Score Statistics (0.0 to 1.0)
    mean_score: float
    median_score: float
    variance_score: float
    std_dev_score: float
    std_error_score: float
    score_ci_95: ConfidenceInterval
    min_score: float
    max_score: float

    # Binary Rate Proportions & 95% Wilson Score Intervals
    task_success_rate: float = Field(ge=0.0, le=1.0)
    task_success_wilson_ci: ConfidenceInterval

    # Trap-fall rate: None / N/A when variant == "control" (since traps are absent)
    trap_fall_rate: float | None = None
    trap_fall_wilson_ci: ConfidenceInterval | None = None
    evidence_violation_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Reliability & Consistency
    parse_failure_episode_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    terminal_decision_consistency: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Modal frequency of (task_success, trap_triggered, terminal_action) across seeds",
    )
    trajectory_jaccard_consistency: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Mean pairwise Jaccard similarity of action sets across all seed pairs",
    )
    pass_at_1: float = Field(default=0.0, ge=0.0, le=1.0)
    pass_all_k: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="1.0 iff all N seeds succeeded without triggering traps, else 0.0 (Pass^k)",
    )

    # Operational Performance
    mean_steps: float = 0.0
    mean_latency_ms: float = 0.0


# --------------------------------------------------------------------------- #
# 4. Benchmark Run Manifest & Top-Level Report
# --------------------------------------------------------------------------- #


class BenchmarkRunManifest(BaseModel):
    run_id: str
    schema_version: str = "2.0.0"
    execution_tier: ExecutionTier
    git_commit_sha: str = "unknown"
    git_is_dirty: bool = False
    environment_versions: dict[str, str] = Field(default_factory=dict)
    seed_config: SeedConfig
    decoding_parameters: DecodingParameters = Field(default_factory=DecodingParameters)
    evaluator_server_url: str = "http://localhost:8000"
    python_version: str = "3.11+"
    platform_info: str = "system"
    started_at_utc: datetime
    completed_at_utc: datetime | None = None


class BenchmarkSuiteReport(BaseModel):
    manifest: BenchmarkRunManifest
    aggregates: list[MultiSeedAggregateResult]
    adversarial_deltas: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Maps model_id -> env_name -> (mean_score_control - mean_score_standard)",
    )
