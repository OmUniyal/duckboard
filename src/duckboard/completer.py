"""Tab-completion for the duckboard REPL."""

from __future__ import annotations

import glob
import os

from collections.abc import Callable
from pathlib import Path

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

_SQL_TABLE_TRIGGERS: frozenset[str] = frozenset({
    "FROM", "JOIN", "INTO", "UPDATE", "TABLE",
    "LEFT", "INNER", "OUTER", "CROSS", "FULL",
})


class DuckboardCompleter:
    def __init__(
        self,
        session: DuckboardSession,
        get_line_buffer: Callable[[], str] | None = None,
    ) -> None:
        self._session = session
        self._get_line_buffer = get_line_buffer
        self._matches: list[str] = []

    def complete(self, text: str, state: int) -> str | None:
        if state == 0:
            matches = self._compute_matches(text)
            if len(matches) == 1:
                # Unique match — complete it fully
                self._matches = matches
            elif len(matches) > 1:
                # Multiple matches — complete to common prefix only
                # This prevents pyreadline3 from flooding the console
                prefix = os.path.commonprefix(matches)
                self._matches = [prefix] if len(prefix) > len(text) else []
            else:
                self._matches = []
        if state == 0:
            return self._matches[0] if self._matches else None
        return None

    def _compute_matches(self, text: str) -> list[str]:
        if self._get_line_buffer is not None:
            line = self._get_line_buffer()
        elif readline is not None and hasattr(readline, "get_line_buffer"):
            line = readline.get_line_buffer()
        else:
            line = text
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

        # ── SQL keyword / table name fallback ─────────────────────────────────
        if not first_is_command:
            # Offer table names after FROM, JOIN, etc.
            prev_token = ""
            if line.endswith(" ") and tokens:
                prev_token = tokens[-1].upper()
            elif len(tokens) >= 2:
                prev_token = tokens[-2].upper()

            if prev_token in _SQL_TABLE_TRIGGERS:
                table_names = [e.name for e in self._session.catalog.list_tables()]
                return [t for t in table_names if t.startswith(text)]

            upper = text.upper()
            return [kw for kw in SQL_KEYWORDS if kw.startswith(upper)]

        return []

    _LOAD_EXTENSIONS = frozenset({
        ".csv", ".tsv", ".psv", ".parquet", ".json", ".jsonl", ".ndjson"
    })

    def _path_matches(self, text: str) -> list[str]:
        leading_quote = text[0] if text and text[0] in ('"', "'") else ""
        raw = text.strip("\"'").replace("\\", "/")
        results: list[str] = []
        for m in sorted(glob.glob(raw + "*")):
            display = m.replace(os.sep, "/")
            if os.path.isdir(m):
                results.append(leading_quote + display + "/")
            elif Path(m).suffix.lower() in self._LOAD_EXTENSIONS:
                results.append(leading_quote + display)
            if len(results) >= 8:
                break
        return results