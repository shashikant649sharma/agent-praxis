"""Deterministic seed derivation and tier resolution utilities."""

from __future__ import annotations

from agent_praxis.framework.runner.multiseed.schemas import (
    ExecutionTier,
    SeedConfig,
    SeedStrategy,
)


def get_tier_seed_config(
    tier: ExecutionTier = ExecutionTier.FULL,
    *,
    explicit_seeds: list[int] | None = None,
    num_seeds: int | None = None,
    strategy: SeedStrategy | None = None,
    base_seed: int = 1000,
) -> SeedConfig:
    """Build a SeedConfig based on execution tier defaults, with optional explicit overrides."""
    if explicit_seeds:
        return SeedConfig(
            strategy=SeedStrategy.EXPLICIT,
            num_seeds=len(explicit_seeds),
            explicit_seeds=list(explicit_seeds),
        )

    # Defaults per tier
    if tier == ExecutionTier.CI:
        default_count = 1
        default_strategy = SeedStrategy.CANONICAL
    elif tier == ExecutionTier.SMOKE:
        default_count = 3
        default_strategy = SeedStrategy.CANONICAL
    elif tier == ExecutionTier.FULL:
        default_count = 5
        default_strategy = SeedStrategy.CANONICAL
    elif tier == ExecutionTier.ROBUSTNESS:
        default_count = 20
        default_strategy = SeedStrategy.CANONICAL
    elif tier == ExecutionTier.RANDOM_CEILING:
        default_count = 40
        default_strategy = SeedStrategy.SEQUENTIAL
        base_seed = 1000
    else:
        default_count = 5
        default_strategy = SeedStrategy.CANONICAL

    return SeedConfig(
        strategy=strategy or default_strategy,
        num_seeds=num_seeds if num_seeds is not None else default_count,
        base_seed=base_seed,
    )


def resolve_seeds_for_suite(
    environments: list[str],
    config: SeedConfig,
) -> dict[str, list[int]]:
    """Resolve the concrete list of integer seeds for every environment in the suite."""
    resolved: dict[str, list[int]] = {}
    for env in environments:
        resolved[env] = config.resolve_seeds(env)
    return resolved
