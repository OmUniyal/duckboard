"""Meta-commands: :load, :tables, :schema, :save, etc."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from duckboard.exceptions import CatalogError
from duckboard.formatter import format_table
from duckboard.session import DuckboardSession

import csv as _csv

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

def _cmd_load(command: str, session: DuckboardSession, input_fn=input) -> str:
    no_header = "--no-header" in command
    clean_command = command.replace("--no-header", "").strip()

    parsed = _parse_load(clean_command)
    if parsed is None:
        return 'Usage: :load "path/to/file.ext" [as name] [--no-header]'
    path_str, name = parsed

    column_names = None
    if no_header:
        ext = Path(path_str).suffix.lower()
        sep = "|" if ext == ".psv" else ","
        col_count = _peek_column_count(path_str, sep)
        if col_count == 0:
            return f"Error: could not read columns from '{path_str}'."
        auto_names = [f"col{i + 1}" for i in range(col_count)]
        user_input = input_fn(
            f"Enter column names (comma-separated) or press Enter for auto "
            f"[{', '.join(auto_names)}]: "
        ).strip()
        if user_input:
            column_names = [c.strip() for c in user_input.split(",")]
            if len(column_names) != col_count:
                return (
                    f"Error: expected {col_count} column names, "
                    f"got {len(column_names)}."
                )
        else:
            column_names = auto_names

    try:
        entry = session.load(name, path_str, no_header=no_header, column_names=column_names)
    except CatalogError as e:
        return f"Error: {e}"

    lines = [f"Loaded '{entry.name}' from {entry.path}  ({entry.format})"]
    for w in session.get_warnings(name):
        lines.append(w)
    if entry.error_count > 0:
        lines.append(
            f"  {entry.error_count} validation error(s) found. "
            f"Run 'SELECT * FROM _errors_{name}' to inspect."
        )
    return "\n".join(lines)


def _cmd_tables(session: DuckboardSession) -> str:
    entries = session.catalog.list_tables()
    if not entries:
        return "(no tables loaded)"
    rows = [
        (
            e.name,
            e.format,
            str(e.path),
            f"[!{e.error_count}]" if e.error_count > 0 else "ok",
        )
        for e in entries
    ]
    return format_table(["name", "format", "path", "errors"], rows)


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


def _infer_format(path: str, flags: list[str]) -> str | None:
    for flag in flags:
        if flag == "--csv":
            return "csv"
        if flag == "--parquet":
            return "parquet"
        if flag == "--json":
            return "json"
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext == ".parquet":
        return "parquet"
    if ext in (".json", ".jsonl", ".ndjson"):
        return "json"
    return None


def _cmd_rename_column(command: str, session: DuckboardSession) -> str:
    parts = command.split()
    if len(parts) != 4:
        return "Usage: :rename_column table old_name new_name"
    _, table, old_col, new_col = parts
    try:
        session.rename_column(table, old_col, new_col)
        return f"Renamed column '{old_col}' to '{new_col}' in '{table}'."
    except CatalogError as e:
        return f"Error: {e}"


def _cmd_export_errors(command: str, session: DuckboardSession) -> str:
    rest = command[len(":export_errors"):].strip().replace("\\", "/")
    try:
        parts = shlex.split(rest)
    except ValueError as e:
        return f"Error: {e}"

    if len(parts) < 2:
        return 'Usage: :export_errors table "path" [--csv|--parquet|--json]'

    table, path = parts[0], parts[1]
    try:
        session.catalog.get(table)
    except CatalogError as e:
        return f"Error: {e}"

    if not session.has_errors(table):
        return f"No errors recorded for '{table}'."

    fmt = _infer_format(path, parts[2:])
    if fmt is None:
        return "Error: could not determine format. Use --csv, --parquet, or --json."

    path_literal = path.replace("'", "''")
    try:
        session.execute(
            f"COPY _errors_{table} TO '{path_literal}' (FORMAT {fmt.upper()}, HEADER)"
        )
        return f"Exported errors for '{table}' to {path}  ({fmt})"
    except Exception as e:
        return f"Error: {e}"


def _cmd_export_clean(command: str, session: DuckboardSession) -> str:
    rest = command[len(":export_clean"):].strip().replace("\\", "/")
    try:
        parts = shlex.split(rest)
    except ValueError as e:
        return f"Error: {e}"

    if len(parts) < 2:
        return 'Usage: :export_clean table "path" [--csv|--parquet|--json]'

    table, path = parts[0], parts[1]
    try:
        session.catalog.get(table)
    except CatalogError as e:
        return f"Error: {e}"

    fmt = _infer_format(path, parts[2:])
    if fmt is None:
        return "Error: could not determine format. Use --csv, --parquet, or --json."

    try:
        cols_info = session.execute(f"DESCRIBE {table}").fetchall()
        col_names = ", ".join(f'"{row[0]}"' for row in cols_info)

        if session.has_errors(table):
            query = (
                f"SELECT {col_names} FROM ("
                f"SELECT *, ROW_NUMBER() OVER () AS _rn FROM {table}"
                f") WHERE _rn NOT IN ("
                f"SELECT row_number FROM _errors_{table} "
                f"WHERE error_type = 'type_anomaly')"
            )
        else:
            query = f"SELECT {col_names} FROM {table}"

        path_literal = path.replace("'", "''")
        session.execute(
            f"COPY ({query}) TO '{path_literal}' (FORMAT {fmt.upper()}, HEADER)"
        )
        return f"Exported clean rows of '{table}' to {path}  ({fmt})"
    except Exception as e:
        return f"Error: {e}"


def _cmd_clear() -> str:
    os.system("cls" if os.name == "nt" else "clear")
    return ""


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _peek_column_count(path: str, sep: str) -> int:
    """Read the first row of a CSV/PSV file and return its field count."""
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = _csv.reader(fh, delimiter=sep)
            first_row = next(reader, None)
            return len(first_row) if first_row else 0
    except Exception:
        return 0

def handle_command(
    command: str,
    session: DuckboardSession,
    last_result=None,
    input_fn=input,
) -> str:
    verb = command.split()[0].lower()
    if verb == ":load":
        return _cmd_load(command, session, input_fn=input_fn)
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
    if verb == ":rename_column":
        return _cmd_rename_column(command, session)
    if verb == ":export_errors":
        return _cmd_export_errors(command, session)
    if verb == ":export_clean":
        return _cmd_export_clean(command, session)
    if verb in (":clear", ":cls"):
        return _cmd_clear()
    return f"Unknown command: {verb}. Type :help for available commands."