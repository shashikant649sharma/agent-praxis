"""Agent Praxis environments package."""

from agent_praxis.environments.catch_22 import environment as catch_22_env
from agent_praxis.environments.dorian_gray import environment as dorian_gray_env
from agent_praxis.environments.metamorphosis import environment as metamorphosis_env
from agent_praxis.environments.nineteen_eighty_four import environment as nineteen_eighty_four_env
from agent_praxis.environments.the_trial import environment as the_trial_env

__all__ = [
    "dorian_gray_env",
    "catch_22_env",
    "nineteen_eighty_four_env",
    "metamorphosis_env",
    "the_trial_env",
]
