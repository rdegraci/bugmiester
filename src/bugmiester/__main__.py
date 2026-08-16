"""CLI entry: `python -m bugmiester`."""

from __future__ import annotations

import argparse

import uvicorn

from bugmiester.config import default_examples_dir, load_settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="bugmiester", description="Bugmiester local server")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        help="Command to run (default: serve). 'analyze' comes in a later slice.",
    )
    args = parser.parse_args(argv)

    if args.command not in {"serve", "run"}:
        raise SystemExit(
            f"Unknown command {args.command!r}. Use: python -m bugmiester"
        )

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


if __name__ == "__main__":
    main()
