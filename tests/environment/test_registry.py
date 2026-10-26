"""Tests for single source of truth environment registry."""

from __future__ import annotations

from agent_praxis.registry import ENVIRONMENT_NAMES, get_factory
from agent_praxis.server import _ENV_FACTORIES as SERVER_FACTORIES


def test_registry_parity_with_server():
    assert set(ENVIRONMENT_NAMES) == set(SERVER_FACTORIES)
    assert len(ENVIRONMENT_NAMES) == 10


def test_every_environment_resolves():
    for name in ENVIRONMENT_NAMES:
        cls = get_factory(name)
        assert callable(cls)
        instance = cls()
        assert instance is not None
        assert hasattr(instance, "reset")
        assert hasattr(instance, "description")
        assert hasattr(instance, "finalize")
