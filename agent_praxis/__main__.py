"""Agent Praxis main entry point."""

from __future__ import annotations

import argparse
import sys

from agent_praxis.commands import environment, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_praxis", description="Agent Praxis — reproducible agent environments.")
    sub = parser.add_subparsers(dest="command")

    env_parser = sub.add_parser("environment", help="Manage an environment.")
    env_parser.add_argument("environment_name", choices=["dorian-gray"], help="Environment name.")
    env_sub = env_parser.add_subparsers(dest="action")
    for action in ("setup", "run", "reset", "evaluate"):
        p = env_sub.add_parser(action)
        p.add_argument("--seed", type=int, default=None, help="Deterministic seed")
    env_parser.set_defaults(func=lambda args: environment.main([args.environment_name, args.action, "--seed", str(args.seed)] if args.seed is not None else [args.environment_name, args.action]))

    val_parser = sub.add_parser("validate", help="Validate an environment.")
    val_parser.add_argument("environment", choices=["dorian-gray"], help="Environment to validate.")
    val_parser.add_argument("--seed", type=int, default=None, help="Deterministic seed")
    val_parser.set_defaults(func=lambda args: validate.main(["dorian-gray", "--seed", str(args.seed)] if args.seed is not None else ["dorian-gray"]))

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        print(f"agent_praxis failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
