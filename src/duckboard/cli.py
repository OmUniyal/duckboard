"""CLI entrypoint — parses args and launches the REPL."""

from __future__ import annotations

import argparse
import sys

from duckboard import __version__

from duckboard.repl import run_repl
from duckboard.session import DuckboardSession


HELP_EPILOG = """
REPL commands:
  :load "path/to/file.ext" [as name]        Load a file as a queryable table
  :tables                                    List all loaded tables
  :schema <table>                            Show column types for a table
  :save "path/to/output.ext"                 Save last query result to file
         [--csv|--parquet|--json]
  :unload <table>                            Remove a loaded table
  :pwd                                       Show current working directory
  :quit / :q / exit / quit / Ctrl+D         Exit duckboard

links:
  Repo:  https://github.com/OmUniyal/duckboard

examples:
  duckboard                  Launch the interactive REPL
  duckboard --version        Print version and exit
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duckboard",
        description=(
            "duckboard — file-first local SQL workspace powered by DuckDB.\n\n"
            "Load CSV, Parquet, and JSON files and query them with plain SQL\n"
            "in an interactive terminal session. No database setup required."
        ),
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"duckboard {__version__}",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    parser.parse_args()

    with DuckboardSession() as session:
        run_repl(session)


if __name__ == "__main__":
    main()