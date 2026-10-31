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
    CONTROL = "control"


SUPPORTED_VARIANTS: list[str] = [v.value for v in EnvironmentVariant]

# Environment-specific variant capability registry.
# Accurately maps each environment to variants that alter ground truth, observations, or execution constraints.
VARIANT_CAPABILITIES: dict[str, list[str]] = {
    "dorian-gray": ["standard"],
    "catch-22": ["standard"],
    "1984": ["standard"],
    "metamorphosis": ["standard"],
    "the-trial": [
        "standard",
        "high_deception",
        "strict_compliance",
        "randomized_invariants",
    ],
    "frankenstein": ["standard"],
    "sorcerers-apprentice": ["standard", "control", "strict_compliance"],
    "sophies-choice": ["standard", "control", "strict_compliance"],
    "library-of-babel": ["standard", "control"],
    "othello": ["standard", "control", "strict_compliance"],
}

ALL_SUPPORTED_VARIANTS: list[tuple[str, str]] = [
    (env, var) for env, variants in VARIANT_CAPABILITIES.items() for var in variants
]


def is_variant_supported(
    environment_name: str,
    variant: str | EnvironmentVariant,
) -> bool:
    """Check whether a given variant is implemented and supported for an environment."""
    norm_env = environment_name.lower().replace("_", "-")
    val = variant.value if isinstance(variant, EnvironmentVariant) else str(variant).lower()
    return val in VARIANT_CAPABILITIES.get(norm_env, ["standard"])


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
    environment_name: str | None = None,
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

    if environment_name is not None and not is_variant_supported(environment_name, var_enum):
        supported = list_supported_variants(environment_name)
        raise ValueError(
            f"Variant '{var_enum.value}' is not supported for environment '{environment_name}'. "
            f"Supported variants: {supported}"
        )

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

    if var_enum == EnvironmentVariant.CONTROL:
        return VariantConfig(
            variant=EnvironmentVariant.CONTROL,
            seed_offset=3003,
            deception_multiplier=0.0,
            strict_ordering=False,
            randomize_identifiers=False,
            metadata={
                "description": (
                    "Control variant condition to measure calibration rather than habitual caution. "
                    "Inverts impossibility or triage constraints to test adaptation to ground truth."
                )
            },
        )

    raise ValueError(f"Unhandled variant: {var_enum}")


def list_supported_variants(environment_name: str | None = None) -> list[str]:
    """Return supported variant profile names for an environment or all globally supported variants."""
    if environment_name is not None:
        norm = environment_name.lower().replace("_", "-")
        return list(VARIANT_CAPABILITIES.get(norm, ["standard"]))
    return list(SUPPORTED_VARIANTS)
