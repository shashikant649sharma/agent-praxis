"""Environment management commands (setup / run / reset / evaluate)."""

from __future__ import annotations

import argparse
from typing import Any

from agent_praxis.environments.dorian_gray import environment as env_mod


def _env_action(*, action: str, seed: int | None = None) -> dict[str, Any]:
    if action not in {"setup", "run", "reset", "evaluate"}:
        raise ValueError(f"Unknown environment action: {action!r}")
    env = env_mod.DorianGrayEnvironment(seed=seed)
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
    p = argparse.ArgumentParser(prog="agent_praxis environment", description="Manage an Agent Praxis environment.")
    sub = p.add_subparsers(dest="environment_name")

    d = sub.add_parser("dorian-gray", help="Dorian Gray environment")
    d.add_argument("action", choices=["setup", "run", "reset", "evaluate"], help="environment action")
    d.add_argument("--seed", type=int, default=None, help="deterministic seed")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.environment_name != "dorian-gray":
        raise SystemExit(f"Unsupported environment: {args.environment_name}")
    try:
        result = _env_action(action=args.action, seed=args.seed)
    except Exception as e:
        raise SystemExit(f"environment command failed: {e}") from e
    import json
    from datetime import datetime, date
    class _DtEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            return super().default(o)
    print(json.dumps(result, indent=2, cls=_DtEncoder))
    return 0
