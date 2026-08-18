"""CLI entry: `python -m bugmiester` / analyze / eval."""

from __future__ import annotations

import argparse
import json

import uvicorn

from bugmiester.analyze import analyze
from bugmiester.config import default_examples_dir, load_settings
from bugmiester.eval import format_report, run_golden_eval


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


def _cmd_eval(*, json_out: bool = False, no_judge: bool = False) -> int:
    report = run_golden_eval(include_mock_judge=not no_judge)
    if json_out:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=False))
    else:
        print(format_report(report))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bugmiester",
        description="Bugmiester local server and ops tools",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=("serve", "run", "analyze", "eval"),
        help="Command to run (default: serve)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="With analyze: print compact JSON (one line)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="With eval: print machine-readable JSON",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="With eval: keyword scoring only (skip mock judge)",
    )
    args = parser.parse_args(argv)

    if args.command in {"serve", "run"}:
        return _cmd_serve()

    if args.command == "analyze":
        return _cmd_analyze(pretty=not args.compact)

    if args.command == "eval":
        return _cmd_eval(json_out=args.json_out, no_judge=args.no_judge)

    print(f"Unknown command {args.command!r}", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
