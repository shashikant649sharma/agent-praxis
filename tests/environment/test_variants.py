"""Tests for the parameterized environment variants system."""

import pytest

from agent_praxis.environments.the_trial.commands import CommandError
from agent_praxis.environments.the_trial.environment import TheTrialEnvironment
from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv
from agent_praxis.framework.variants import (
    SUPPORTED_VARIANTS,
    VariantConfig,
    get_variant_config,
    list_supported_variants,
)


def test_supported_variants_list():
    assert "standard" in SUPPORTED_VARIANTS
    assert "high_deception" in SUPPORTED_VARIANTS
    assert "strict_compliance" in SUPPORTED_VARIANTS
    assert "randomized_invariants" in SUPPORTED_VARIANTS
    assert list_supported_variants() == SUPPORTED_VARIANTS


def test_get_variant_config_properties():
    cfg_std = get_variant_config("standard")
    assert isinstance(cfg_std, VariantConfig)
    assert cfg_std.deception_multiplier == 1.0
    assert cfg_std.strict_ordering is False
    assert cfg_std.randomize_identifiers is False

    cfg_high = get_variant_config("high_deception")
    assert cfg_high.deception_multiplier > 1.0

    cfg_strict = get_variant_config("strict_compliance")
    assert cfg_strict.strict_ordering is True

    cfg_rand = get_variant_config("randomized_invariants", seed=12345)
    assert cfg_rand.randomize_identifiers is True


def test_get_variant_config_unknown_raises():
    with pytest.raises(ValueError, match="Unknown variant 'mythical'"):
        get_variant_config("mythical")


def test_the_trial_standard_variant_baseline():
    env = TheTrialEnvironment(seed=19250426, variant="standard")
    assert env.variant == "standard"
    docket = env.inspect_court_docket()
    assert "URGENT MAGISTRATE DIRECTIVE" in docket["clerk_advisory"]
    assert env._state.ground_truth.required_nonce == "CH-9941-NONCE"


def test_the_trial_high_deception_variant():
    env = TheTrialEnvironment(seed=19250426, variant="high_deception")
    assert env.variant == "high_deception"
    docket = env.inspect_court_docket()
    assert "CRITICAL COURT DECREE" in docket["clerk_advisory"]


def test_the_trial_strict_compliance_variant():
    env = TheTrialEnvironment(seed=19250426, variant="strict_compliance")
    assert env.variant == "strict_compliance"

    env.query_court_records()
    env.examine_precedent_archive()

    # Skipping inspect_court_docket under strict compliance raises CommandError
    with pytest.raises(CommandError, match="Strict compliance requires inspecting court docket"):
        env.assemble_formal_petition()

    # Once docket is inspected, petition drafting succeeds
    env.inspect_court_docket()
    res = env.assemble_formal_petition()
    assert res["result"] == "petition_assembled"


def test_the_trial_randomized_invariants_variant():
    env1 = TheTrialEnvironment(seed=19250426, variant="randomized_invariants")
    env2 = TheTrialEnvironment(seed=42424242, variant="randomized_invariants")

    # Invariants should be randomized based on seed and not match hardcoded CH-9941-NONCE
    gt1 = env1._state.ground_truth
    gt2 = env2._state.ground_truth
    assert gt1.required_nonce != "CH-9941-NONCE"
    assert gt1.required_nonce != gt2.required_nonce
    assert gt1.required_provenance != gt2.required_provenance


def test_gymnasium_wrapper_variant_integration():
    env = AgentPraxisGymEnv(environment="the-trial", seed=19250426, variant="high_deception")
    _obs, info = env.reset()
    assert info["variant"] == "high_deception"
    # Action 2 is inspect_court_docket
    obs, _reward, _terminated, _truncated, _info = env.step(2)
    assert "CRITICAL COURT DECREE" in obs


@pytest.mark.parametrize(
    "env_name,class_path",
    [
        ("dorian-gray", "agent_praxis.environments.dorian_gray.environment.DorianGrayEnvironment"),
        ("catch-22", "agent_praxis.environments.catch_22.environment.Catch22Environment"),
        (
            "1984",
            "agent_praxis.environments.nineteen_eighty_four.environment.NineteenEightyFourEnvironment",
        ),
        (
            "metamorphosis",
            "agent_praxis.environments.metamorphosis.environment.MetamorphosisEnvironment",
        ),
        (
            "frankenstein",
            "agent_praxis.environments.frankenstein.environment.FrankensteinEnvironment",
        ),
        ("the-trial", "agent_praxis.environments.the_trial.environment.TheTrialEnvironment"),
    ],
)
@pytest.mark.parametrize(
    "variant", ["standard", "high_deception", "strict_compliance", "randomized_invariants"]
)
def test_all_environments_instantiate_and_reset_variants(env_name, class_path, variant):
    import importlib

    mod_name, cls_name = class_path.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)

    env = cls(seed=20260101, variant=variant)
    assert env.variant == variant
    assert env.variant_config.variant.value == variant

    # Reset with a different variant
    res = env.reset(variant="strict_compliance")
    assert env.variant == "strict_compliance"
    assert res.get("variant") == "strict_compliance"


def test_gymnasium_all_environments_variant_support():
    for env_name in [
        "dorian-gray",
        "catch-22",
        "1984",
        "metamorphosis",
        "the-trial",
        "frankenstein",
    ]:
        gym_env = AgentPraxisGymEnv(
            environment=env_name, seed=20260101, variant="strict_compliance"
        )
        _obs, info = gym_env.reset()
        assert info["variant"] == "strict_compliance"
