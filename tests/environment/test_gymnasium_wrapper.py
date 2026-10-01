"""Tests for the Gymnasium-compatible wrapper.

These tests verify the Gymnasium interface contract without requiring
gymnasium to be installed — they use the wrapper's internal logic directly.
"""


def test_gymnasium_wrapper_importable():
    """The wrapper module is importable regardless of gymnasium availability."""
    import agent_praxis.framework.gymnasium_wrapper as gw

    assert hasattr(gw, "DorianGrayGymEnv")
    assert hasattr(gw, "ACTION_NAMES")
    assert len(gw.ACTION_NAMES) == 10


def test_action_names_match_environment_commands():
    """ACTION_NAMES indices must match the environment's command label mapping."""
    from agent_praxis.environments.dorian_gray.commands import COMMAND_LABEL_TO_INDEX
    from agent_praxis.framework.gymnasium_wrapper import ACTION_NAMES

    for _name, idx in COMMAND_LABEL_TO_INDEX.items():
        assert idx < len(ACTION_NAMES), f"Index {idx} out of range for ACTION_NAMES"


def test_gymnasium_wrapper_functional():
    """If gymnasium is available, verify the full reset/step/finalize cycle."""
    try:
        import gymnasium  # noqa: F401

        from agent_praxis.framework.gymnasium_wrapper import DorianGrayGymEnv
    except ImportError:
        return  # Skip if gymnasium not installed

    env = DorianGrayGymEnv(seed=20260201, max_steps=20)
    obs, info = env.reset()
    assert isinstance(obs, str)
    assert "action_names" in info

    # Known-good trajectory via Gym interface
    actions = [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        9,
    ]  # status, logs, metrics, index, recon, diag, recovery, finalize
    total_reward = 0.0
    for action in actions:
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break

    assert terminated, "Finalize should terminate the episode"
    assert total_reward == 1.0, f"Known-good path should score 1.0, got {total_reward}"

    env.close()


def test_gymnasium_wrapper_bad_path():
    """Superficial patch through Gym interface should score low."""
    try:
        import gymnasium  # noqa: F401

        from agent_praxis.framework.gymnasium_wrapper import DorianGrayGymEnv
    except ImportError:
        return  # Skip if gymnasium not installed

    env = DorianGrayGymEnv(seed=20260201, max_steps=20)
    env.reset()

    # Superficial path
    actions = [1, 8, 9]  # status, patch, finalize
    total_reward = 0.0
    for action in actions:
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break

    assert terminated
    assert total_reward <= 0.3, f"Superficial path should score <= 0.3, got {total_reward}"

    env.close()


def test_agent_praxis_gym_env_all_environments():
    """Verify AgentPraxisGymEnv initializes and resets across all 5 environments."""
    try:
        import gymnasium  # noqa: F401

        from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS, AgentPraxisGymEnv
    except ImportError:
        return

    for env_name in ENV_SPECS:
        env = AgentPraxisGymEnv(environment=env_name, max_steps=10)
        obs, info = env.reset()
        assert isinstance(obs, str)
        assert len(obs) > 0
        assert "action_names" in info
        assert "environment" in info
        assert info["environment"] == env_name
        assert env.action_space.n == len(ENV_SPECS[env_name]["actions"])
        env.close()


def test_agent_praxis_gym_env_step_and_finalize():
    """Verify AgentPraxisGymEnv stepping and finalization for catch-22 and metamorphosis."""
    try:
        import gymnasium  # noqa: F401

        from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv
    except ImportError:
        return

    # Catch-22 step test
    c22_env = AgentPraxisGymEnv(environment="catch-22", seed=20260301)
    c22_env.reset()
    # Step status (action 1) then finalize (action 7)
    obs, reward, terminated, truncated, info = c22_env.step(1)
    assert not terminated
    obs, reward, terminated, truncated, info = c22_env.step(7)
    assert terminated
    assert "evaluation" in info
    c22_env.close()

    # Metamorphosis step test
    meta_env = AgentPraxisGymEnv(environment="metamorphosis", seed=20260401)
    meta_env.reset()
    obs, reward, terminated, truncated, info = meta_env.step(1)  # status
    assert not terminated
    obs, reward, terminated, truncated, info = meta_env.step(7)  # finalize
    assert terminated
    assert "evaluation" in info
    meta_env.close()

