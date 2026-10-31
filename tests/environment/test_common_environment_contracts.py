"""Parameterized contract tests validating shared invariants across all 10 environments.

Tests standard invariants:
1. Command category completeness (read, inspect, act).
2. AllowedCommand immutability.
3. Information hiding: agent-facing descriptions strip evaluator metadata (note, restricted_target).
4. Evaluator metadata retention when explicitly requested.
5. Command index integrity (0..N-1 with contiguous indexing).
6. Deterministic reset behavior across identical seeds.
7. Terminal lifecycle enforcement (post-finalize mutation raises CommandError).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agent_praxis.environments import (
    catch_22,
    dorian_gray,
    frankenstein,
    library_of_babel,
    metamorphosis,
    nineteen_eighty_four,
    othello,
    sophies_choice,
    sorcerers_apprentice,
    the_trial,
)
from agent_praxis.errors import CommandError

ENV_PACKAGES = [
    ("dorian-gray", dorian_gray, dorian_gray.environment.DorianGrayEnvironment),
    ("catch-22", catch_22, catch_22.environment.Catch22Environment),
    ("1984", nineteen_eighty_four, nineteen_eighty_four.environment.NineteenEightyFourEnvironment),
    ("metamorphosis", metamorphosis, metamorphosis.environment.MetamorphosisEnvironment),
    ("the-trial", the_trial, the_trial.environment.TheTrialEnvironment),
    ("frankenstein", frankenstein, frankenstein.environment.FrankensteinEnvironment),
    (
        "sorcerers-apprentice",
        sorcerers_apprentice,
        sorcerers_apprentice.environment.SorcerersApprenticeEnvironment,
    ),
    (
        "sophies-choice",
        sophies_choice,
        sophies_choice.environment.SophiesChoiceEnvironment,
    ),
    (
        "library-of-babel",
        library_of_babel,
        library_of_babel.environment.LibraryOfBabelEnvironment,
    ),
    (
        "othello",
        othello,
        othello.environment.OthelloEnvironment,
    ),
]


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_command_categories(env_name: str, pkg: object, cls: type) -> None:
    commands_mod = pkg.commands
    allowed = commands_mod.ALLOWED_COMMANDS
    cat_enum = commands_mod.CommandCategory

    categories = {cmd.category for cmd in allowed}
    assert cat_enum.read in categories
    assert cat_enum.inspect in categories
    assert cat_enum.act in categories


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_command_immutability(env_name: str, pkg: object, cls: type) -> None:
    commands_mod = pkg.commands
    first_cmd = commands_mod.ALLOWED_COMMANDS[0]
    with pytest.raises(FrozenInstanceError):
        first_cmd.name = "mutated_command"  # type: ignore[misc]


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_agent_observation_sanitization(
    env_name: str, pkg: object, cls: type
) -> None:
    commands_mod = pkg.commands
    agent_desc = commands_mod.describe_allowed_commands(include_evaluator_metadata=False)
    assert len(agent_desc) == len(commands_mod.ALLOWED_COMMANDS)

    for item in agent_desc:
        assert set(item.keys()) == {"category", "name", "description"}
        assert "restricted_target" not in item
        assert "note" not in item


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_evaluator_metadata_retention(
    env_name: str, pkg: object, cls: type
) -> None:
    commands_mod = pkg.commands
    eval_desc = commands_mod.describe_allowed_commands(include_evaluator_metadata=True)
    assert len(eval_desc) == len(commands_mod.ALLOWED_COMMANDS)

    for item in eval_desc:
        assert {"category", "name", "description", "restricted_target", "note"}.issubset(
            set(item.keys())
        )


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_command_indexing_integrity(env_name: str, pkg: object, cls: type) -> None:
    commands_mod = pkg.commands
    allowed = commands_mod.ALLOWED_COMMANDS
    mapping = commands_mod.COMMAND_LABEL_TO_INDEX

    assert len(mapping) == len(allowed)
    assert set(mapping.keys()) == {cmd.name for cmd in allowed}
    assert set(mapping.values()) == set(range(len(allowed)))


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_reset_determinism(env_name: str, pkg: object, cls: type) -> None:
    env1 = cls(seed=424242)
    obs1 = env1.reset()
    env2 = cls(seed=424242)
    obs2 = env2.reset()

    assert obs1 == obs2


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_finalize_guard(env_name: str, pkg: object, cls: type) -> None:
    env = cls(seed=424242)
    env.reset()
    env.finalize()

    # Second finalize must raise CommandError
    with pytest.raises(CommandError):
        env.finalize()


@pytest.mark.parametrize("env_name,pkg,cls", ENV_PACKAGES)
def test_all_environments_finalize_safe_payload(env_name: str, pkg: object, cls: type) -> None:
    """Ensure finalize() across all environments returns strictly {'finalized', 'seed'},
    leaking zero internal evaluator flags or outcome states."""
    env = cls(seed=424242)
    fin = env.finalize()
    assert isinstance(fin, dict)
    assert set(fin.keys()) == {"finalized", "seed"}
    assert fin["finalized"] is True
    assert fin["seed"] == 424242
