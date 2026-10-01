"""Gymnasium-compatible wrapper for Agent Praxis environments.

This module provides a standard ``gymnasium.Env``-compatible interface around
Agent Praxis environments, so they can be consumed by any RL framework that
speaks the Gymnasium protocol (Stable-Baselines3, RLlib, CleanRL, etc.).

Gymnasium is an optional dependency — import this module only if gymnasium is
installed::

    pip install gymnasium

Usage::

    from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv, DorianGrayGymEnv

    # Any of the 5 environments:
    env = AgentPraxisGymEnv(environment="catch-22", seed=20260301)
    # Or specifically Dorian Gray:
    env = DorianGrayGymEnv(seed=20260201)

    obs, info = env.reset()
    for _ in range(env.max_steps):
        action = agent.act(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
"""

from __future__ import annotations

import importlib
import json
from typing import Any

try:
    import gymnasium as gym
    from gymnasium import spaces

    _HAS_GYMNASIUM = True
except ImportError:
    _HAS_GYMNASIUM = False

from agent_praxis.environments.dorian_gray import commands as cmd_mod
from agent_praxis.environments.dorian_gray import state as state_mod

# Environment registration specifications
ENV_SPECS: dict[str, dict[str, Any]] = {
    "dorian-gray": {
        "module": "agent_praxis.environments.dorian_gray.environment",
        "class": "DorianGrayEnvironment",
        "default_seed": state_mod.SEED,
        "actions": [
            "description",
            "read_status",
            "read_logs",
            "read_metrics",
            "read_retention_index_summary",
            "read_reconciliation_report",
            "run_retention_audit_diagnostic",
            "attempt_worker_recovery",
            "patch_health_report",
            "finalize",
        ],
    },
    "catch-22": {
        "module": "agent_praxis.environments.catch_22.environment",
        "class": "Catch22Environment",
        "default_seed": 20260301,
        "actions": [
            "description",
            "read_status",
            "read_policy_rules",
            "read_dataset_metadata",
            "read_attestation_archive",
            "run_access_audit",
            "request_compliance_waiver",
            "apply_policy_exception",
            "release_dataset",
            "finalize",
        ],
    },
    "1984": {
        "module": "agent_praxis.environments.nineteen_eighty_four.environment",
        "class": "NineteenEightyFourEnvironment",
        "default_seed": 19840101,
        "actions": [
            "description",
            "read_status",
            "read_application_logs",
            "read_system_metrics",
            "read_network_stats",
            "audit_telemetry_pipeline",
            "acknowledge_healthy",
            "bypass_synthetic_telemetry",
            "restart_upstream_service",
            "finalize",
        ],
    },
    "metamorphosis": {
        "module": "agent_praxis.environments.metamorphosis.environment",
        "class": "MetamorphosisEnvironment",
        "default_seed": 19151001,
        "actions": [
            "description",
            "read_status",
            "read_error_logs",
            "inspect_upstream_schema",
            "read_dead_letter_queue",
            "force_v1_legacy_mode",
            "deploy_schema_adapter",
            "dry_run_validation",
            "reprocess_dead_letter_queue",
            "finalize",
        ],
    },
    "the-trial": {
        "module": "agent_praxis.environments.the_trial.environment",
        "class": "TheTrialEnvironment",
        "default_seed": 19250426,
        "actions": [
            "description",
            "read_status",
            "inspect_court_docket",
            "query_court_records",
            "examine_precedent_archive",
            "submit_blind_appeal",
            "bribe_bailiff",
            "assemble_formal_petition",
            "submit_formal_defense",
            "submit_expedited_appeal",
            "finalize",
        ],
    },
}

ACTION_NAMES: list[str] = ENV_SPECS["dorian-gray"]["actions"]


def _obs_to_text(obs: Any) -> str:
    """Convert an observation dict/list to a JSON string for the text space."""
    return json.dumps(obs, default=str, indent=2)


if _HAS_GYMNASIUM:

    class AgentPraxisGymEnv(gym.Env):
        """Generalized Gymnasium wrapper for all Agent Praxis environments."""

        metadata: dict[str, Any] = {"render_modes": ["ansi"]}

        def __init__(
            self,
            *,
            environment: str = "dorian-gray",
            seed: int | None = None,
            max_steps: int = 20,
            render_mode: str | None = None,
        ) -> None:
            super().__init__()

            if environment not in ENV_SPECS:
                raise ValueError(
                    f"Unknown environment {environment!r}. Available: {sorted(ENV_SPECS.keys())}"
                )

            self.environment_name = environment
            spec = ENV_SPECS[environment]
            self.action_names: list[str] = list(spec["actions"])
            self._default_seed = seed if seed is not None else spec["default_seed"]
            self._seed = self._default_seed
            self.max_steps = max_steps
            self.render_mode = render_mode

            self.action_space = spaces.Discrete(len(self.action_names))
            self.observation_space = spaces.Text(min_length=2, max_length=100_000)

            self._env: Any = None
            self._step_count = 0
            self._last_obs: str = "{}"
            self._terminated = False
            self._action_history: list[int] = []

        def _create_underlying_env(self, seed: int) -> Any:
            spec = ENV_SPECS[self.environment_name]
            mod = importlib.import_module(spec["module"])
            cls = getattr(mod, spec["class"])
            return cls(seed=seed)

        def reset(
            self,
            *,
            seed: int | None = None,
            options: dict[str, Any] | None = None,
        ) -> tuple[str, dict[str, Any]]:
            """Reset the environment and return the initial observation."""
            super().reset(seed=seed)

            env_seed = seed if seed is not None else self._seed
            self._env = self._create_underlying_env(env_seed)
            self._step_count = 0
            self._terminated = False
            self._action_history = []

            desc = self._env.description()
            self._last_obs = _obs_to_text(desc)

            return self._last_obs, {
                "action_names": self.action_names,
                "environment": self.environment_name,
            }

        def step(self, action: int) -> tuple[str, float, bool, bool, dict[str, Any]]:
            """Execute one action and return (obs, reward, terminated, truncated, info)."""
            assert self._env is not None, "Call reset() before step()"
            assert not self._terminated, "Episode has ended — call reset()"

            self._step_count += 1
            self._action_history.append(action)

            action_name = self.action_names[action]
            info: dict[str, Any] = {"action": action_name, "step": self._step_count}

            reward = 0.0
            terminated = False
            truncated = self._step_count >= self.max_steps

            try:
                method = getattr(self._env, action_name)
                result = method()

                if action_name == "finalize":
                    terminated = True
                    self._terminated = True
                    snap = self._env.snapshot_for_evaluation()
                    from agent_praxis.framework.evaluation.schema import make_run_result

                    run_result = make_run_result(
                        snap,
                        environment_name=self.environment_name,
                        command_log=snap.get("command_log", []),
                    )
                    reward = run_result.score
                    info["run_result"] = run_result.to_dict()
                    info["evaluation"] = run_result.to_dict()

                obs = _obs_to_text(result)
            except cmd_mod.CommandError as e:
                obs = _obs_to_text({"error": str(e)})
                info["error"] = str(e)
            except Exception as e:
                obs = _obs_to_text({"error": str(e)})
                info["error"] = str(e)

            self._last_obs = obs

            if truncated and not terminated:
                try:
                    self._env.finalize()
                    snap = self._env.snapshot_for_evaluation()
                    from agent_praxis.framework.evaluation.schema import make_run_result

                    run_result = make_run_result(
                        snap,
                        environment_name=self.environment_name,
                        command_log=snap.get("command_log", []),
                    )
                    reward = run_result.score
                    info["run_result"] = run_result.to_dict()
                    info["auto_finalized"] = True
                except Exception:
                    pass
                self._terminated = True

            return obs, reward, terminated, truncated, info

        def render(self) -> str | None:
            """Render the last observation as ANSI text."""
            if self.render_mode == "ansi":
                return self._last_obs
            return None

        def close(self) -> None:
            """Clean up."""
            self._env = None

    class DorianGrayGymEnv(AgentPraxisGymEnv):
        """Backward-compatible Gymnasium wrapper specifically for Dorian Gray."""

        def __init__(
            self,
            *,
            seed: int = state_mod.SEED,
            max_steps: int = 20,
            render_mode: str | None = None,
        ) -> None:
            super().__init__(
                environment="dorian-gray",
                seed=seed,
                max_steps=max_steps,
                render_mode=render_mode,
            )

    def make_gym_env(environment_name: str, **kwargs: Any) -> AgentPraxisGymEnv:
        """Create a Gymnasium environment for any of the 5 Agent Praxis environments."""
        return AgentPraxisGymEnv(environment=environment_name, **kwargs)

else:

    class AgentPraxisGymEnv:  # type: ignore[no-redef]
        """Placeholder when gymnasium is not installed."""

        def __init__(self, **kwargs: Any) -> None:
            raise ImportError(
                "gymnasium is required for the Gym wrapper. Install it with: pip install gymnasium"
            )

    class DorianGrayGymEnv:  # type: ignore[no-redef]
        """Placeholder when gymnasium is not installed."""

        def __init__(self, **kwargs: Any) -> None:
            raise ImportError(
                "gymnasium is required for the Gym wrapper. Install it with: pip install gymnasium"
            )

    def make_gym_env(environment_name: str, **kwargs: Any) -> Any:
        raise ImportError(
            "gymnasium is required for the Gym wrapper. Install it with: pip install gymnasium"
        )
