"""Agent Praxis main entry point."""

from __future__ import annotations

import argparse
import sys

from agent_praxis.commands import demo, environment, validate
from agent_praxis.registry import ENVIRONMENT_NAMES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="praxis", description="Agent Praxis — reproducible agent environments."
    )
    sub = parser.add_subparsers(dest="command")

    demo_parser = sub.add_parser(
        "demo",
        help="Display side-by-side baseline policy comparisons or execute live demonstrations.",
    )
    demo_parser.add_argument(
        "--live",
        action="store_true",
        help="Execute policies live in-memory instead of displaying cached canonical summary.",
    )
    demo_parser.add_argument(
        "--env",
        choices=list(ENVIRONMENT_NAMES) + ["all"],
        default=None,
        help="Target environment (default: all for summary, '1984' for live)",
    )
    demo_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic seed for live execution (default: 42)",
    )
    demo_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output results as JSON",
    )
    demo_parser.add_argument(
        "--markdown",
        action="store_true",
        help="Format output as a Markdown table",
    )
    demo_parser.set_defaults(func=lambda args: demo.main_args(args))

    ALL_ENVS = list(ENVIRONMENT_NAMES)
    env_parser = sub.add_parser("environment", help="Manage an environment.")
    env_parser.add_argument("environment_name", choices=ALL_ENVS, help="Environment name.")
    env_sub = env_parser.add_subparsers(dest="action")
    for action in ("setup", "run", "reset", "evaluate"):
        p = env_sub.add_parser(action)
        p.add_argument("--seed", type=int, default=None, help="Deterministic seed")
    env_parser.set_defaults(
        func=lambda args: environment.main(
            [args.environment_name, args.action, "--seed", str(args.seed)]
            if args.seed is not None
            else [args.environment_name, args.action]
        )
    )

    val_parser = sub.add_parser("validate", help="Validate an environment.")
    val_parser.add_argument("environment", choices=ALL_ENVS, help="Environment to validate.")
    val_parser.add_argument("--seed", type=int, default=None, help="Deterministic seed")
    val_parser.set_defaults(
        func=lambda args: validate.main(
            [args.environment, "--seed", str(args.seed)]
            if args.seed is not None
            else [args.environment]
        )
    )

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        ret = args.func(args)
        return int(ret) if isinstance(ret, int) else 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        print(f"agent_praxis failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
