from __future__ import annotations

import argparse
import json
import sys

from .config import load_config
from .controller import Controller, make_provider
from .errors import LifecycleError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="abliteration-station")
    root.add_argument("--config", help="JSON configuration path")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("ensure", help="Start the first usable provider and run model gates")
    stop = commands.add_parser("stop", help="Stop the active provider without deleting persistent data")
    stop.add_argument("--provider", choices=["vast"])
    commands.add_parser("status", help="Show provider and route state")
    commands.add_parser("doctor", help="Show missing configuration without starting compute")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        controller = Controller(load_config(args.config))
        if args.command == "ensure":
            route = controller.ensure()
            print(json.dumps({"provider": route.provider, "upstream": route.upstream, "identity": route.identity}))
        elif args.command == "stop":
            controller.stop(args.provider)
            print(json.dumps({"stopped": args.provider or "active"}))
        elif args.command == "status":
            print(json.dumps(controller.status(), indent=2, sort_keys=True))
        elif args.command == "doctor":
            report = controller.doctor()
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1 if all(report.values()) else 0
        return 0
    except (LifecycleError, OSError, ValueError, KeyError) as error:
        print(f"abliteration-station: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
