"""CLI entry: `python -m bugmiester` / `python -m bugmiester analyze`."""

from __future__ import annotations

import argparse
import json

import uvicorn

from bugmiester.analyze import analyze
from bugmiester.config import default_examples_dir, load_settings


def _cmd_serve() -> int:
    settings = load_settings(examples_dir=default_examples_dir())
    # Standing rule: localhost only.
    host = "127.0.0.1"
    port = settings.server.port

    print(f"Bugmiester listening on http://{host}:{port}")
    print(f"App dir: {settings.app_dir}")
    print(f"Config ready: {settings.config_ready} (provider={settings.llm.provider})")
    if not settings.config_ready and settings.missing_key:
        print(f"Set {settings.missing_key} in {settings.env_path}")

    uvicorn.run(
        "bugmiester.app:app",
        host=host,
        port=port,
        reload=False,
    )
    return 0


def _cmd_analyze(*, pretty: bool = True) -> int:
    settings = load_settings(examples_dir=default_examples_dir())
    summary = analyze(
        settings.reports_dir,
        settings.logs_dir,
        persist=True,
    )
    if pretty:
        print(json.dumps(summary, indent=2, sort_keys=False))
    else:
        print(json.dumps(summary, sort_keys=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bugmiester",
        description="Bugmiester local server and ops tools",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=("serve", "run", "analyze"),
        help="Command to run (default: serve)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="With analyze: print compact JSON (one line)",
    )
    args = parser.parse_args(argv)

    if args.command in {"serve", "run"}:
        return _cmd_serve()

    if args.command == "analyze":
        return _cmd_analyze(pretty=not args.compact)

    print(f"Unknown command {args.command!r}", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
