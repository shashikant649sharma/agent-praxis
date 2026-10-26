"""Environment management commands (setup / run / reset / evaluate)."""

from __future__ import annotations

import argparse
import json
from typing import Any, cast

from agent_praxis.registry import ENVIRONMENT_NAMES, get_factory
from agent_praxis.utils import DateTimeEncoder

_ENV_FACTORIES: dict[str, Any] = {name: get_factory(name) for name in ENVIRONMENT_NAMES}


def _env_action(*, env_name: str, action: str, seed: int | None = None) -> dict[str, Any]:
    if action not in {"setup", "run", "reset", "evaluate"}:
        raise ValueError(f"Unknown environment action: {action!r}")
    if env_name not in _ENV_FACTORIES:
        raise ValueError(f"Unsupported environment: {env_name!r}")

    cls = _ENV_FACTORIES[env_name]
    env: Any = cls(seed=seed) if seed is not None else cls()
    if action == "setup":
        return {"action": "setup", "seed": env.seed, "description": env.description()}
    if action == "reset":
        return cast("dict[str, Any]", env.reset())
    if action == "run":
        return {"action": "run", "status": env.read_status()}
    if action == "evaluate":
        env.finalize()
        return cast("dict[str, Any]", env.snapshot_for_evaluation())
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
