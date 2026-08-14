"""CLI entry point for duckboard."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duckboard",
        description="File-first local SQL workspace powered by DuckDB.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.0.0",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    print("duckboard: not yet implemented — REPL coming soon.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
