"""Single source of truth for the environment registry.

Factories are lazy so importing this module stays cheap and does not pull in
the evaluator's web stack.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

_FACTORIES: dict[str, tuple[str, str]] = {
    "dorian-gray": ("agent_praxis.environments.dorian_gray.environment", "DorianGrayEnvironment"),
    "catch-22": ("agent_praxis.environments.catch_22.environment", "Catch22Environment"),
    "1984": (
        "agent_praxis.environments.nineteen_eighty_four.environment",
        "NineteenEightyFourEnvironment",
    ),
    "metamorphosis": (
        "agent_praxis.environments.metamorphosis.environment",
        "MetamorphosisEnvironment",
    ),
    "the-trial": ("agent_praxis.environments.the_trial.environment", "TheTrialEnvironment"),
    "frankenstein": (
        "agent_praxis.environments.frankenstein.environment",
        "FrankensteinEnvironment",
    ),
    "sorcerers-apprentice": (
        "agent_praxis.environments.sorcerers_apprentice.environment",
        "SorcerersApprenticeEnvironment",
    ),
    "sophies-choice": (
        "agent_praxis.environments.sophies_choice.environment",
        "SophiesChoiceEnvironment",
    ),
    "library-of-babel": (
        "agent_praxis.environments.library_of_babel.environment",
        "LibraryOfBabelEnvironment",
    ),
    "othello": ("agent_praxis.environments.othello.environment", "OthelloEnvironment"),
}

ENVIRONMENT_NAMES: tuple[str, ...] = tuple(_FACTORIES)


def get_factory(name: str) -> Callable[..., Any]:
    """Dynamically load and return the environment class for the given name."""
    if name not in _FACTORIES:
        raise KeyError(f"Unknown environment: {name!r}. Available: {ENVIRONMENT_NAMES}")
    module_path, class_name = _FACTORIES[name]
    return cast("Callable[..., Any]", getattr(importlib.import_module(module_path), class_name))
