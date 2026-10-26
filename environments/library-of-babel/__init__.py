"""Compatibility shim for environments/library-of-babel."""

from agent_praxis.environments.library_of_babel import commands, environment, evidence, state
from agent_praxis.environments.library_of_babel.environment import LibraryOfBabelEnvironment

__all__ = [
    "commands",
    "environment",
    "evidence",
    "state",
    "LibraryOfBabelEnvironment",
]
