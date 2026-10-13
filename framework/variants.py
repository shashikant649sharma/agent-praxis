"""Canonical variants module proxy for framework package."""

from agent_praxis.framework.variants import (
    SUPPORTED_VARIANTS,
    EnvironmentVariant,
    VariantConfig,
    get_variant_config,
    list_supported_variants,
)

__all__ = [
    "EnvironmentVariant",
    "VariantConfig",
    "SUPPORTED_VARIANTS",
    "get_variant_config",
    "list_supported_variants",
]
