"""Interactive REPL for duckboard."""

from __future__ import annotations

import sys

from duckboard.exceptions import DuckboardError
from duckboard.formatter import format_table
from duckboard.session import DuckboardSession

EXIT_TRIGGERS = frozenset({":quit", ":q", "exit", "quit"})

PROMPT_MAIN = "duckboard> "
PROMPT_CONT = "        -> "

try:
    if sys.platform == "win32":
        import pyreadline3  # noqa: F401
    else:
        import readline  # noqa: F401
except ImportError:
    pass


def _read_input(prompt: str) -> str:
    """Wrap input() so callers only handle EOFError at the top level."""
    return input(prompt)


def _is_command(line: str) -> bool:
    return line.startswith(":")


def _is_exit(line: str) -> bool:
    return line.lower() in EXIT_TRIGGERS


def run_repl(session: DuckboardSession) -> None:
    from duckboard.commands import handle_command

    buffer: list[str] = []

    while True:
        prompt = PROMPT_MAIN if not buffer else PROMPT_CONT
        try:
            raw = _read_input(prompt)
        except EOFError:
            print("\nBye.")
            break

        line = raw.strip()

        # Empty line — reset buffer, back to fresh prompt
        if not line:
            buffer = []
            continue

        # Exit triggers (single-line only)
        if _is_exit(line):
            print("Bye.")
            break

        # Commands (single-line only, no accumulation)
        if _is_command(line):
            try:
                result = handle_command(line, session)
                if result:
                    print(result)
            except DuckboardError as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"Error: {e}")
            buffer = []
            continue

        # SQL accumulation
        buffer.append(raw)

        joined = " ".join(b.strip() for b in buffer)
        if not joined.rstrip().endswith(";"):
            continue

        # Semicolon seen — execute
        sql = joined.rstrip().rstrip(";").strip()
        buffer = []

        try:
            cols, rows = session.fetch(sql)
            print(format_table(cols, rows))
        except DuckboardError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")