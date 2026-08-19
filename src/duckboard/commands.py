"""Meta-commands: :load, :tables, :schema, :save, etc."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from duckboard.exceptions import CatalogError
from duckboard.formatter import format_table
from duckboard.session import DuckboardSession

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_LOAD_RE = re.compile(
    r'^:load\s+'
    r'(?:"(?P<quoted>[^"]+)"|(?P<unquoted>\S+))'
    r'(?:\s+as\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*))?'
    r'\s*$',
    re.IGNORECASE,
)

_SAVE_FORMATS = {"--csv": "csv", "--parquet": "parquet", "--json": "json"}
_LARGE_ROW_WARNING = 2_000


def _normalize_path(path_str: str) -> str:
    """Normalize to forward slashes for cross-platform DuckDB compatibility."""
    return path_str.replace("\\", "/")


def _parse_load(command: str) -> tuple[str, str] | None:
    """Return (path_str, name) or None if parse fails."""
    m = _LOAD_RE.match(command.strip())
    if not m:
        return None
    path_str = _normalize_path(m.group("quoted") or m.group("unquoted"))
    name = m.group("name") or Path(path_str).stem
    return path_str, name


def _parse_save(command: str) -> tuple[str, str | None] | None:
    """Return (path_str, explicit_format | None) or None if parse fails."""
    # Replace backslashes before shlex sees them — shlex treats \ as escape char
    parts = shlex.split(command.replace("\\", "/"))
    # parts: [":save", "output.csv"] or [":save", "output.csv", "--parquet"]
    if len(parts) < 2 or len(parts) > 3:
        return None
    path_str = parts[1]
    explicit = None
    if len(parts) == 3:
        if parts[2] not in _SAVE_FORMATS:
            return None
        explicit = _SAVE_FORMATS[parts[2]]
    return path_str, explicit


def _format_of(path_str: str) -> str | None:
    ext = Path(path_str).suffix.lower()
    return {".csv": "csv", ".parquet": "parquet", ".json": "json"}.get(ext)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_load(command: str, session: DuckboardSession) -> str:
    parsed = _parse_load(command)
    if parsed is None:
        return 'Usage: :load "path/to/file.ext" [as name]'
    path_str, name = parsed
    try:
        entry = session.load(name, path_str)
        return f"Loaded '{entry.name}' from {entry.path}  ({entry.format})"
    except CatalogError as e:
        return f"Error: {e}"


def _cmd_tables(session: DuckboardSession) -> str:
    entries = session.catalog.list_tables()
    if not entries:
        return "(no tables loaded)"
    rows = [(e.name, e.format, str(e.path)) for e in entries]
    return format_table(["name", "format", "path"], rows)


def _cmd_schema(command: str, session: DuckboardSession) -> str:
    parts = command.split()
    if len(parts) != 2:
        return "Usage: :schema <table>"
    name = parts[1]
    try:
        columns, rows = session.schema(name)
        return format_table(columns, rows)
    except CatalogError as e:
        return f"Error: {e}"


def _cmd_save(
    command: str,
    last_result: tuple[list[str], list[tuple]] | None,
) -> str:
    if last_result is None:
        return "No query result to save. Run a SELECT query first."

    parsed = _parse_save(command)
    if parsed is None:
        return 'Usage: :save "path/to/output.ext" [--csv|--parquet|--json]'

    path_str, explicit_fmt = parsed
    fmt = explicit_fmt or _format_of(path_str)
    if fmt is None:
        return (
            f"Cannot detect format from '{path_str}'. "
            "Use --csv, --parquet, or --json."
        )

    cols, rows = last_result
    total = len(rows)

    if total >= _LARGE_ROW_WARNING:
        answer = input(
            f"{total:,} rows will be exported. Continue? [Y/N] "
        ).strip().lower()
        if answer != "y":
            return "Export cancelled."

    try:
        import duckdb
        conn = duckdb.connect()
        placeholders = ", ".join("?" * len(cols))
        col_defs = ", ".join(f'"{c}" VARCHAR' for c in cols)
        conn.execute(f"CREATE TEMP TABLE _save_buf ({col_defs})")
        conn.executemany(
            f"INSERT INTO _save_buf VALUES ({placeholders})", rows
        )
        out = Path(path_str)
        out_str = str(out).replace("\\", "/")
        if fmt == "csv":
            conn.execute(f"COPY _save_buf TO '{out_str}' (FORMAT CSV, HEADER)")
        elif fmt == "parquet":
            conn.execute(f"COPY _save_buf TO '{out_str}' (FORMAT PARQUET)")
        elif fmt == "json":
            conn.execute(f"COPY _save_buf TO '{out_str}' (FORMAT JSON)")
        conn.close()
        return f"Saved {total:,} {'row' if total == 1 else 'rows'} to {out}"
    except Exception as e:
        return f"Error saving file: {e}"


def _cmd_unload(command: str, session: DuckboardSession) -> str:
    parts = command.split()
    if len(parts) != 2:
        return "Usage: :unload <table>"
    name = parts[1]
    try:
        session.unload(name)
        return f"Unloaded '{name}'."
    except CatalogError as e:
        return f"Error: {e}"


def _cmd_pwd() -> str:
    return os.getcwd()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def handle_command(
    command: str,
    session: DuckboardSession,
    last_result: tuple[list[str], list[tuple]] | None = None,
) -> str:
    verb = command.split()[0].lower()
    if verb == ":load":
        return _cmd_load(command, session)
    if verb == ":tables":
        return _cmd_tables(session)
    if verb == ":schema":
        return _cmd_schema(command, session)
    if verb == ":save":
        return _cmd_save(command, last_result)
    if verb == ":unload":
        return _cmd_unload(command, session)
    if verb == ":pwd":
        return _cmd_pwd()
    return f"Unknown command: {verb}. Type :help for available commands."