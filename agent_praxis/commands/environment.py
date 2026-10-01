"""Environment management commands (setup / run / reset / evaluate)."""

from __future__ import annotations

import argparse
import json
from typing import Any

from agent_praxis.environments import (
    catch_22_env,
    dorian_gray_env,
    metamorphosis_env,
    nineteen_eighty_four_env,
    the_trial_env,
)
from agent_praxis.utils import DateTimeEncoder

_ENV_FACTORIES = {
    "dorian-gray": dorian_gray_env.DorianGrayEnvironment,
    "catch-22": catch_22_env.Catch22Environment,
    "1984": nineteen_eighty_four_env.NineteenEightyFourEnvironment,
    "metamorphosis": metamorphosis_env.MetamorphosisEnvironment,
    "the-trial": the_trial_env.TheTrialEnvironment,
}


def _env_action(*, env_name: str, action: str, seed: int | None = None) -> dict[str, Any]:
    if action not in {"setup", "run", "reset", "evaluate"}:
        raise ValueError(f"Unknown environment action: {action!r}")
    if env_name not in _ENV_FACTORIES:
        raise ValueError(f"Unsupported environment: {env_name!r}")

    cls = _ENV_FACTORIES[env_name]
    env = cls(seed=seed)
    if action == "setup":
        return {"action": "setup", "seed": env.seed, "description": env.description()}
    if action == "reset":
        return env.reset()
    if action == "run":
        return {"action": "run", "status": env.read_status()}
    if action == "evaluate":
        env.finalize()
        return env.snapshot_for_evaluation()
    raise AssertionError("unreachable")


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent_praxis environment", description="Manage an Agent Praxis environment."
    )
    sub = p.add_subparsers(dest="environment_name")

    for name in _ENV_FACTORIES:
        s = sub.add_parser(name, help=f"{name} environment")
        s.add_argument(
            "action", choices=["setup", "run", "reset", "evaluate"], help="environment action"
        )
        s.add_argument("--seed", type=int, default=None, help="deterministic seed")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if not args.environment_name or args.environment_name not in _ENV_FACTORIES:
        raise SystemExit(f"Unsupported or missing environment: {args.environment_name}")
    try:
        result = _env_action(env_name=args.environment_name, action=args.action, seed=args.seed)
    except Exception as e:
        raise SystemExit(f"environment command failed: {e}") from e
    print(json.dumps(result, indent=2, cls=DateTimeEncoder))
    return 0
