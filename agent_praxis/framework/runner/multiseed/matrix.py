"""Workload matrix expander: Cartesian product with round-robin interleaving."""

from __future__ import annotations

from typing import Literal

from agent_praxis.framework.runner.multiseed.schemas import (
    DecodingParameters,
    EpisodeSpec,
    SeedConfig,
)
from agent_praxis.framework.runner.multiseed.seeds import resolve_seeds_for_suite


def expand_workload_matrix(
    models: list[tuple[str, str]],  # List of (model_id, provider)
    environments: list[str],
    variants: list[Literal["standard", "control"]],
    seed_config: SeedConfig,
    decoding: DecodingParameters | None = None,
) -> list[EpisodeSpec]:
    """Expand models × environments × variants × seeds into an interleaved list of EpisodeSpecs.

    Interleaving by (seed, env, model) ensures concurrent workers distribute load across
    different environments and providers rather than hammering a single API or environment.
    """
    dec = decoding or DecodingParameters()
    seeds_by_env = resolve_seeds_for_suite(environments, seed_config)

    # Determine maximum number of seeds across all environments
    max_seeds = max(len(s) for s in seeds_by_env.values()) if seeds_by_env else 0

    specs: list[EpisodeSpec] = []
    # Interleave: seed index first, then variant, then environment, then model
    for s_idx in range(max_seeds):
        for variant in variants:
            for env in environments:
                env_seeds = seeds_by_env.get(env, [])
                if s_idx >= len(env_seeds):
                    continue
                seed = env_seeds[s_idx]
                for model_id, provider in models:
                    specs.append(
                        EpisodeSpec(
                            provider=provider,
                            model_id=model_id,
                            environment_name=env,
                            variant=variant,
                            seed=seed,
                            decoding=dec,
                        )
                    )

    return specs
