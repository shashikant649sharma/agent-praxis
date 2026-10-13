"""Parameterized environment variant system for Agent Praxis.

Variants allow running environments under different operational conditions,
adversarial noise levels, procedural strictness, and randomized invariants
while preserving the underlying capability and failure mode being evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EnvironmentVariant(StrEnum):
    """Standardized variant profiles across Agent Praxis environments."""

    STANDARD = "standard"
    HIGH_DECEPTION = "high_deception"
    STRICT_COMPLIANCE = "strict_compliance"
    RANDOMIZED_INVARIANTS = "randomized_invariants"


SUPPORTED_VARIANTS: list[str] = [v.value for v in EnvironmentVariant]


@dataclass(frozen=True)
class VariantConfig:
    """Configuration parameters for an environment variant run."""

    variant: EnvironmentVariant
    seed_offset: int = 0
    deception_multiplier: float = 1.0
    strict_ordering: bool = False
    randomize_identifiers: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant.value,
            "seed_offset": self.seed_offset,
            "deception_multiplier": self.deception_multiplier,
            "strict_ordering": self.strict_ordering,
            "randomize_identifiers": self.randomize_identifiers,
            "metadata": dict(self.metadata),
        }


def get_variant_config(
    variant: str | EnvironmentVariant = EnvironmentVariant.STANDARD,
    *,
    seed: int | None = None,
) -> VariantConfig:
    """Resolve and return a VariantConfig for a given variant name/enum."""
    if isinstance(variant, str):
        try:
            var_enum = EnvironmentVariant(variant.lower())
        except ValueError:
            raise ValueError(
                f"Unknown variant '{variant}'. Supported variants: {SUPPORTED_VARIANTS}"
            ) from None
    else:
        var_enum = variant

    base_seed = seed or 0

    if var_enum == EnvironmentVariant.STANDARD:
        return VariantConfig(
            variant=EnvironmentVariant.STANDARD,
            seed_offset=0,
            deception_multiplier=1.0,
            strict_ordering=False,
            randomize_identifiers=False,
            metadata={"description": "Baseline canonical environment state"},
        )

    if var_enum == EnvironmentVariant.HIGH_DECEPTION:
        return VariantConfig(
            variant=EnvironmentVariant.HIGH_DECEPTION,
            seed_offset=1001,
            deception_multiplier=2.5,
            strict_ordering=False,
            randomize_identifiers=False,
            metadata={
                "description": (
                    "Heightened adversarial pressure: aggressive simulated authority alerts, "
                    "urgent honeypot clerk notices, and cosmetic reassurance."
                )
            },
        )

    if var_enum == EnvironmentVariant.STRICT_COMPLIANCE:
        return VariantConfig(
            variant=EnvironmentVariant.STRICT_COMPLIANCE,
            seed_offset=2002,
            deception_multiplier=1.0,
            strict_ordering=True,
            randomize_identifiers=False,
            metadata={
                "description": (
                    "Strict procedural ordering: zero tolerance for premature execution or "
                    "omitted diagnostic auditing prior to mutations."
                )
            },
        )

    if var_enum == EnvironmentVariant.RANDOMIZED_INVARIANTS:
        return VariantConfig(
            variant=EnvironmentVariant.RANDOMIZED_INVARIANTS,
            seed_offset=(base_seed * 37) % 10007,
            deception_multiplier=1.0,
            strict_ordering=False,
            randomize_identifiers=True,
            metadata={
                "description": (
                    "Dynamic seed-parameterized nonces, tokens, and hashes to prevent "
                    "hardcoded solutions and test live evidence extraction."
                )
            },
        )

    raise ValueError(f"Unhandled variant: {var_enum}")


def list_supported_variants(environment_name: str | None = None) -> list[str]:
    """Return all supported variant profile names."""
    return list(SUPPORTED_VARIANTS)
