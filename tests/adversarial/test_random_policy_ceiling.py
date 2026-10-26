"""Regression test ensuring uniform random policies cannot solve environments by chance.

Asserts that across all 10 environments over 20 random seeds:
- Success rate is strictly 0%
- Max score across all runs is bounded < 0.60 (empirically <= 0.45)
"""

from __future__ import annotations

import pytest

from agent_praxis.registry import ENVIRONMENT_NAMES
from tools.random_baseline import run_random_agent

SEEDS = [1000 + i for i in range(20)]


@pytest.mark.parametrize("env_name", list(ENVIRONMENT_NAMES))
def test_random_policy_bounded_below_ceiling(env_name: str) -> None:
    runs = [run_random_agent(env_name, seed=s, max_steps=16) for s in SEEDS]
    scores = [r["score"] for r in runs]
    successes = [r for r in runs if r["task_success"]]

    assert len(successes) == 0, f"Random policy solved {env_name}: {successes}"
    max_score = max(scores)
    assert max_score < 0.60, f"{env_name} exceeded random ceiling: max_score={max_score}"


@pytest.mark.parametrize(
    "variant", ["high_deception", "strict_compliance", "randomized_invariants"]
)
@pytest.mark.parametrize(
    "env_name", ["dorian-gray", "catch-22", "1984", "the-trial", "sorcerers-apprentice"]
)
def test_random_policy_variants_bounded_below_ceiling(env_name: str, variant: str) -> None:
    """Random agent must not solve non-standard variants by chance."""
    variant_seeds = [2000, 2001, 2002]
    runs = [
        run_random_agent(env_name, seed=s, variant=variant, max_steps=16) for s in variant_seeds
    ]
    for r in runs:
        assert not r["task_success"], (
            f"Random policy accidentally solved {env_name} under {variant}: {r}"
        )
        assert r["score"] < 0.60, (
            f"Random policy score too high on {env_name} under {variant}: {r['score']}"
        )
