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

_DELIMITER_ALIASES: dict[str, str] = {
    "tab": "\t",
    "pipe": "|",
    "semicolon": ";",
    "caret": "^",
    "comma": ",",
}


_QUOTECHAR_RE = re.compile(r'--quotechar\s+(\S+)')


def _resolve_delimiter(value: str) -> str:
    """Expand alias or return value as-is (single or multi-char)."""
    return _DELIMITER_ALIASES.get(value.lower(), value)

_SAVE_FORMATS = {"--csv": "csv", "--parquet": "parquet", "--json": "json"}
_LARGE_ROW_WARNING = 2_000


def _normalize_path(path_str: str) -> str:
    """Normalize to forward slashes for cross-platform DuckDB compatibility."""
    return path_str.replace("\\", "/")


def _parse_load(
    command: str,
) -> tuple[str, str, bool, str | None, str | None]:
    """Return (path_str, name, no_header, delimiter, quotechar).

    Raises ValueError with a user-facing message on any parse failure.
    """
    rest = command[len(":load"):].strip().replace("\\", "/")

    # Pre-extract --quotechar before shlex sees it — bare quote chars confuse shlex
    quotechar_pre: str | None = None
    qm = _QUOTECHAR_RE.search(rest)
    if qm:
        raw_val = qm.group(1)
        # Strip outer matching quotes if present (e.g. "'" → ')
        if len(raw_val) >= 2 and raw_val[0] == '"' and raw_val[-1] == '"':
            quotechar_pre = raw_val[1:-1]
        elif len(raw_val) >= 2 and raw_val[0] == "'" and raw_val[-1] == "'":
            quotechar_pre = raw_val[1:-1]
        else:
            quotechar_pre = raw_val
        rest = rest[: qm.start()] + rest[qm.end() :]

    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        raise ValueError(f"Could not parse :load command: {exc}") from exc

    if not tokens:
        raise ValueError(
            'Usage: :load "path/to/file.ext" [as name] '
            "[--no-header] [--delimiter <value>] [--quotechar <char>]"
        )

    path_str = _normalize_path(tokens[0])
    tokens = tokens[1:]

    name: str | None = None
    if len(tokens) >= 2 and tokens[0].lower() == "as":
        name = tokens[1]
        tokens = tokens[2:]
    if name is None:
        name = Path(path_str).stem

    no_header = False
    delimiter: str | None = None
    quotechar: str | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--no-header":
            no_header = True
            i += 1
        elif tok == "--delimiter":
            if i + 1 >= len(tokens):
                raise ValueError("--delimiter requires a value.")
            delimiter = _resolve_delimiter(tokens[i + 1])
            i += 2
        elif tok == "--quotechar":
            # Should have been pre-extracted; if it appears here the value
            # was quoted by the user (e.g. --quotechar "|") — handle it.
            if i + 1 >= len(tokens):
                raise ValueError("--quotechar requires a value.")
            qc = tokens[i + 1]
            if len(qc) != 1:
                raise ValueError(
                    f"--quotechar must be a single character, got {qc!r}."
                )
            quotechar = qc
            i += 2
        else:
            raise ValueError(f"Unknown flag: {tok!r}.")

    if quotechar_pre is not None:
        if len(quotechar_pre) != 1:
            raise ValueError(
                f"--quotechar must be a single character, got {quotechar_pre!r}."
            )
        if quotechar is None:  # don't override if token loop also found one
            quotechar = quotechar_pre

    return path_str, name, no_header, delimiter, quotechar


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
    try:
        path_str, name, no_header, delimiter, quotechar = _parse_load(command)
    except ValueError as exc:
        return str(exc)

    column_names = None
    if no_header:
        ext = Path(path_str).suffix.lower()
        peek_sep = delimiter if delimiter is not None else ("|" if ext == ".psv" else ",")
        if len(peek_sep) > 1:
            peek_sep = ","  # multi-char: fall back for peeking only
        col_count = _peek_column_count(path_str, peek_sep)
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
        entry = session.load(
            name, path_str,
            no_header=no_header, column_names=column_names,
            delimiter=delimiter, quotechar=quotechar,
        )
    except CatalogError as e:
        return f"Error: {e}"

    lines = [f"Loaded '{entry.name}' from {entry.path}  ({entry.format})"]

    warnings = session.get_warnings(name)
    residual_warns = [w for w in warnings if "dropped by DuckDB" in w]
    other_warns    = [w for w in warnings if "dropped by DuckDB" not in w]

    for w in other_warns:
        lines.append(f"  {w}")

    has_errors   = entry.error_count > 0
    has_residual = bool(residual_warns)

    if has_errors and has_residual:
        lines.append(
            f"  {entry.error_count} error(s) found, plus rows dropped by DuckDB (cause unknown)."
        )
        lines.append(f"  → :export_errors {name}  to inspect known errors")
    elif has_errors:
        lines.append(f"  {entry.error_count} validation error(s) found.")
        lines.append(
            f"  → :export_errors {name}  to inspect"
            f"  |  :export_clean {name}  for clean rows"
        )
    elif has_residual:
        for w in residual_warns:
            lines.append(f"  {w}")
        lines.append(f"  → :export_errors {name}  for any captured errors")

    return "\n".join(lines)


def _cmd_tables(session: DuckboardSession) -> str:
    entries = session.catalog.list_tables()
    if not entries:
        return "(no tables loaded)"
    rows = []
    for e in entries:
        warns = session.get_warnings(e.name)
        has_residual = any("dropped by DuckDB" in w for w in warns)
        if e.error_count > 0 and has_residual:
            status = f"[!{e.error_count} +?]"
        elif e.error_count > 0:
            status = f"[!{e.error_count}]"
        elif has_residual:
            status = "[!?]"
        else:
            status = "ok"
        rows.append((e.name, e.format, str(e.path), status))
    return format_table(["name", "format", "path", "errors"], rows)


def _cmd_schema(command: str, session: DuckboardSession) -> str:
    parts = command.split()
    if len(parts) != 2:
        return "Usage: :schema <table>"
    name = parts[1]
    try:
        entry = session.catalog.get(name)
        columns, rows = session.schema(name)
        result = format_table(columns, rows)
        if entry.format in ("csv", "psv"):
            delim_display = (
                repr(entry.delimiter) if entry.delimiter is not None else "(default)"
            )
            quote_display = (
                repr(entry.quotechar) if entry.quotechar is not None else '(default: ")'
            )
            result += f"\n\nDelimiter : {delim_display}"
            result += f"\nQuote char: {quote_display}"
        warnings = session.get_warnings(name)
        if warnings:
            result += "\n\nWarnings:\n" + "\n".join(f"  {w}" for w in warnings)
        return result
    except CatalogError as e:
        return f"Error: {e}"


def _cmd_save(
    command: str,
    last_result: tuple[list[str], list[tuple]] | None,
    input_fn=input,
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
        answer = input_fn(
            f"{total:,} rows will be exported. Continue? [Y/N] "
        ).strip().lower()
        if answer != "y":
            return "Export cancelled."

    out = Path(path_str)
    try:
        if fmt == "csv":
            with out.open("w", newline="", encoding="utf-8") as f:
                writer = _csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
        elif fmt == "json":
            import json
            with out.open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(dict(zip(cols, (None if v == "NULL" else v for v in row))), default=str) + "\n")
        elif fmt == "parquet":
            import duckdb
            conn = duckdb.connect()
            col_defs = ", ".join(f'"{c}" VARCHAR' for c in cols)
            placeholders = ", ".join("?" * len(cols))
            conn.execute(f"CREATE TEMP TABLE _save_buf ({col_defs})")
            conn.execute("BEGIN TRANSACTION")
            conn.executemany(f"INSERT INTO _save_buf VALUES ({placeholders})", rows)
            conn.execute("COMMIT")
            out_str = str(out).replace("\\", "/")
            conn.execute(f"COPY _save_buf TO '{out_str}' (FORMAT PARQUET)")
            conn.close()
        return f"Saved {total:,} {'row' if total == 1 else 'rows'} to {out}"
    except KeyboardInterrupt:
        return "Export cancelled."
    except Exception as e:
        return f"Error saving file: {e}"


def _cmd_unload(command: str, session: DuckboardSession) -> str:
    parts = command.split()
    if len(parts) != 2:
        return "Usage: :unload <table>  |  :unload all"
    name = parts[1]

    if name.lower() == "all":
        entries = session.catalog.list_tables()
        if not entries:
            return "(no tables loaded)"
        unloaded, failed = [], []
        for e in entries:
            try:
                session.unload(e.name)
                unloaded.append(e.name)
            except CatalogError as ex:
                failed.append(f"{e.name}: {ex}")
        lines = [f"Unloaded {len(unloaded)} table(s): {', '.join(unloaded)}."]
        lines.extend(failed)
        return "\n".join(lines)

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
        return _cmd_save(command, last_result, input_fn=input_fn)
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