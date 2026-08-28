"""Tab-completion for the duckboard REPL."""

from __future__ import annotations

import glob
import os

from duckboard.session import DuckboardSession

try:
    if __import__("sys").platform == "win32":
        import pyreadline3 as readline  # type: ignore[import]
    else:
        import readline  # type: ignore[import]
except ImportError:
    readline = None  # type: ignore[assignment]


COMMANDS: list[str] = [
    ":clear",
    ":cls",
    ":export_clean",
    ":export_errors",
    ":load",
    ":pwd",
    ":q",
    ":quit",
    ":rename_column",
    ":save",
    ":schema",
    ":tables",
    ":unload",
]

TABLE_ARG_COMMANDS: frozenset[str] = frozenset({
    ":export_clean",
    ":export_errors",
    ":rename_column",
    ":save",
    ":schema",
    ":unload",
})

PATH_ARG_COMMANDS: frozenset[str] = frozenset({":load"})

SQL_KEYWORDS: list[str] = [
    "AND", "AS", "AVG", "BY", "CASE", "COUNT", "CREATE", "DELETE",
    "DISTINCT", "DROP", "ELSE", "END", "FROM", "GROUP", "HAVING",
    "IN", "INNER", "INSERT", "IS", "JOIN", "LEFT", "LIKE", "LIMIT",
    "MAX", "MIN", "NOT", "NULL", "ON", "OR", "ORDER", "SELECT",
    "SUM", "THEN", "UPDATE", "WHEN", "WHERE", "WITH",
]


class DuckboardCompleter:
    def __init__(self, session: DuckboardSession) -> None:
        self._session = session
        self._matches: list[str] = []

    def complete(self, text: str, state: int) -> str | None:
        if state == 0:
            self._matches = self._compute_matches(text)
        try:
            return self._matches[state]
        except IndexError:
            return None

    def _compute_matches(self, text: str) -> list[str]:
        line = readline.get_line_buffer() if readline is not None else text
        tokens = line.split()

        # ── Completing the first token (command name) ────────────────────────
        first_is_command = tokens and tokens[0].startswith(":")
        completing_first = not tokens or (len(tokens) == 1 and not line.endswith(" "))

        if completing_first and (not text or text.startswith(":")):
            return [c for c in COMMANDS if c.startswith(text)]

        # ── Completing arguments ─────────────────────────────────────────────
        if not tokens:
            return []

        cmd = tokens[0]

        # Table name argument
        if cmd in TABLE_ARG_COMMANDS and (
            len(tokens) == 1 or (len(tokens) == 2 and not line.endswith(" "))
        ):
            table_names = [
                e.name for e in self._session.catalog.list_tables()
            ]
            return [t for t in table_names if t.startswith(text)]

        # File path argument
        if cmd in PATH_ARG_COMMANDS and (
            len(tokens) == 1 or (len(tokens) == 2 and not line.endswith(" "))
        ):
            return self._path_matches(text)

        # ── SQL keyword fallback ─────────────────────────────────────────────
        if not first_is_command:
            upper = text.upper()
            return [kw for kw in SQL_KEYWORDS if kw.startswith(upper)]

        return []

    @staticmethod
    def _path_matches(text: str) -> list[str]:
        raw = text.strip("\"'")
        matches = glob.glob(raw + "*")
        results: list[str] = []
        for m in matches:
            display = m.replace(os.sep, "/")
            if os.path.isdir(m):
                display += "/"
            results.append(display)
        return results