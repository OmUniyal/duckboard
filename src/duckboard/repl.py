"""Interactive REPL for duckboard."""

from __future__ import annotations

import re
import sys

from duckboard.exceptions import DuckboardError
from duckboard.formatter import format_table
from duckboard.session import DuckboardSession

EXIT_TRIGGERS = frozenset({":quit", ":q", "exit", "quit"})

PROMPT_MAIN = "duckboard> "
PROMPT_CONT = "        -> "

_HINT_RE = re.compile(
    r"/\*\+\s*vertical_result\s*\(\s*(\d+)\s*\)\s*\*/",
    re.IGNORECASE,
)


def _read_input(prompt: str) -> str:
    """Wrap input() so callers only handle EOFError at the top level."""
    return input(prompt)


def _is_command(line: str) -> bool:
    return line.startswith(":")


def _is_exit(line: str) -> bool:
    return line.lower() in EXIT_TRIGGERS


def run_repl(session: DuckboardSession, _input_fn=None) -> None:
    from duckboard.commands import handle_command

    _test_mode = _input_fn is not None
    if _input_fn is None:
        _input_fn = _read_input

    if not _test_mode:
        try:
            from duckboard.completer import DuckboardCompleter

            if sys.platform == "win32":
                from pyreadline3 import Readline as _Readline  # type: ignore[import]
                _rl = _Readline()
                _completer = DuckboardCompleter(session, get_line_buffer=_rl.get_line_buffer)
                _rl.set_completer(_completer.complete)
                _rl.set_completer_delims(" \t")
                _rl.parse_and_bind("tab: complete")
                _input_fn = _rl.readline
            else:
                import readline as _rl  # type: ignore[import]
                _completer = DuckboardCompleter(session, get_line_buffer=_rl.get_line_buffer)
                _rl.set_completer(_completer.complete)
                _rl.set_completer_delims(" \t")
                if getattr(_rl, "__doc__", None) and "libedit" in _rl.__doc__:
                    _rl.parse_and_bind("bind ^I rl_complete")  # macOS libedit
                else:
                    _rl.parse_and_bind("tab: complete")
        except (ImportError, AttributeError):
            pass  # readline / pyreadline3 not installed or API unavailable — silent

    buffer: list[str] = []
    last_result: tuple[list[str], list[tuple]] | None = None

    while True:
        prompt = PROMPT_MAIN if not buffer else PROMPT_CONT
        try:
            raw = _input_fn(prompt)
        except EOFError:
            print("\nBye.")
            break
        except KeyboardInterrupt:
            print("\nInterrupted. Type :quit to exit.")
            buffer = []
            continue

        line = raw.strip()

        if not line:
            buffer = []
            continue

        if _is_exit(line):
            print("Bye.")
            break

        if _is_command(line):
            try:
                result = handle_command(line, session, last_result)
                if result:
                    print(result)
            except KeyboardInterrupt:
                print("\nInterrupted.")
            except DuckboardError as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"Error: {e}")
            buffer = []
            continue

        buffer.append(raw)

        joined = " ".join(b.strip() for b in buffer)
        if not joined.rstrip().endswith(";"):
            continue

        # Semicolon seen — parse vertical triggers, then execute
        raw_sql = joined.rstrip()
        vertical = False
        vert_max_rows = 50

        if raw_sql.endswith("\\G;"):
            vertical = True
            raw_sql = raw_sql[:-3] + ";"

        sql = raw_sql.rstrip(";").strip()

        hint_match = _HINT_RE.search(sql)
        if hint_match:
            vertical = True
            vert_max_rows = int(hint_match.group(1))
            sql = _HINT_RE.sub("", sql).strip()

        buffer = []

        try:
            cols, rows = session.fetch(sql)
            last_result = (cols, rows)
            print(format_table(cols, rows, max_rows=vert_max_rows, vertical=vertical))
        except KeyboardInterrupt:
            print("\nInterrupted.")
        except DuckboardError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")