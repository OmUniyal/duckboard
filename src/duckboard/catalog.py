"""File catalog — register paths as queryable table/view names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

from duckboard.exceptions import CatalogError

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_CSV_EXTENSIONS = {".csv", ".tsv"}
_PSV_EXTENSIONS = {".psv"}
_PARQUET_EXTENSIONS = {".parquet"}
_JSON_EXTENSIONS = {".json", ".jsonl", ".ndjson"}


@dataclass(frozen=True)
class CatalogEntry:
    """One registered file."""

    name: str
    path: Path
    format: str  # "csv", "psv", "parquet", or "json"
    error_count: int = 0  # structural + type-anomaly errors from validation


def _validate_name(name: str) -> None:
    if not _NAME_PATTERN.match(name):
        raise CatalogError(
            f"Invalid table name {name!r}. Use letters, numbers, underscore; "
            "must not start with a number."
        )


def _detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _CSV_EXTENSIONS:
        return "csv"
    if ext in _PSV_EXTENSIONS:
        return "psv"
    if ext in _PARQUET_EXTENSIONS:
        return "parquet"
    if ext in _JSON_EXTENSIONS:
        return "json"
    raise CatalogError(
        f"Unsupported file type {ext!r} for {path}. "
        "Supported: .csv, .tsv, .psv, .parquet, .json, .jsonl, .ndjson"
    )


def _read_function(
    fmt: str,
    path: Path,
    no_header: bool = False,
    column_names: list[str] | None = None,
) -> str:
    """Return DuckDB read_* SQL for a file path."""
    path_literal = str(path.resolve()).replace("\\", "/").replace("'", "''")
    extras = _header_clause(no_header, column_names)
    if fmt == "csv":
        return f"read_csv_auto('{path_literal}', ignore_errors=true{extras})"
    if fmt == "psv":
        return f"read_csv_auto('{path_literal}', sep='|', ignore_errors=true{extras})"
    if fmt == "parquet":
        return f"read_parquet('{path_literal}')"
    if fmt == "json":
        return f"read_json_auto('{path_literal}')"
    raise CatalogError(f"Unknown format: {fmt}")


def _csv_sep(fmt: str) -> str:
    return "|" if fmt == "psv" else ","


def _header_clause(no_header: bool, column_names: list[str] | None) -> str:
    """Extra read_csv_auto args when the file has no header row."""
    if not no_header:
        return ""
    if column_names:
        quoted = ", ".join(f"'{c}'" for c in column_names)
        return f", header=false, names=[{quoted}]"
    return ", header=false"


class FileCatalog:
    """Register files as DuckDB views queryable by name."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._entries: dict[str, CatalogEntry] = {}
        self._warnings: dict[str, list[str]] = {}

    def load(
        self,
        name: str,
        path: str | Path,
        no_header: bool = False,
        column_names: list[str] | None = None,
    ) -> CatalogEntry:
        _validate_name(name)

        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise CatalogError(f"File not found: {resolved}")

        fmt = _detect_format(resolved)
        read_fn = _read_function(fmt, resolved, no_header=no_header, column_names=column_names)

        self._conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {read_fn}")

        self._warnings[name] = []
        error_count = 0

        if fmt in ("csv", "psv"):
            if not no_header and self._no_header_heuristic(name):
                self._warnings[name].append(
                    f"Warning: first row of '{name}' may be data, not headers. "
                    "Use ':load ... --no-header' if needed."
                )
            error_count += self._run_structural_validation(name, resolved, fmt)
            error_count += self._run_type_anomaly_detection(name)

        entry = CatalogEntry(name=name, path=resolved, format=fmt, error_count=error_count)
        self._entries[name] = entry
        return entry

    def list_tables(self) -> list[CatalogEntry]:
        return sorted(self._entries.values(), key=lambda e: e.name)

    def get(self, name: str) -> CatalogEntry:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise CatalogError(f"Table {name!r} is not loaded.") from exc

    def unload(self, name: str) -> None:
        if name not in self._entries:
            raise CatalogError(f"No table named '{name}' is loaded.")
        self._conn.execute(f"DROP VIEW IF EXISTS {name}")
        self._conn.execute(f"DROP TABLE IF EXISTS _errors_{name}")
        del self._entries[name]
        self._warnings.pop(name, None)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _no_header_heuristic(self, name: str) -> bool:
        """Return True if any column name looks like a data value, not a label."""
        try:
            cols = self._conn.execute(f"DESCRIBE {name}").fetchall()
            return any(
                re.match(r"^\d+(\.\d+)?$", row[0]) or row[0].lower() in ("true", "false")
                for row in cols
            )
        except Exception:
            return False

    def _ensure_errors_table(self, name: str) -> None:
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS _errors_{name} (
                row_number  INTEGER,
                raw_line    VARCHAR,
                error_type  VARCHAR,
                column_name VARCHAR,
                reason      VARCHAR
            )
        """)

    def _run_structural_validation(self, name: str, path: Path, fmt: str) -> int:
        import csv as _csv

        sep = _csv_sep(fmt)
        errors: list[tuple[int, str, str]] = []

        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as fh:
                reader = _csv.reader(fh, delimiter=sep)
                try:
                    header = next(reader)
                except StopIteration:
                    return 0
                expected = len(header)

                for i, row in enumerate(reader, start=2):
                    if i > 1000:
                        break
                    if len(row) != expected:
                        raw = sep.join(row)
                        reason = (
                            f"column count mismatch: expected {expected}, got {len(row)}"
                        )
                        errors.append((i, raw, reason))
        except Exception:
            return 0

        if not errors:
            return 0

        self._ensure_errors_table(name)
        for row_number, raw_line, reason in errors:
            self._conn.execute(
                f"INSERT INTO _errors_{name} VALUES (?, ?, 'structural', NULL, ?)",
                [row_number, raw_line, reason],
            )
        return len(errors)

    def _run_type_anomaly_detection(self, name: str) -> int:
        """
        For each VARCHAR column: if <5% of non-null values in the first 1,000
        rows are numeric, those rows are flagged as type anomalies.
        Returns the number of anomalous values found.
        """
        try:
            col_info = self._conn.execute(f"DESCRIBE {name}").fetchall()
        except Exception:
            return 0

        varchar_cols = [
            row[0] for row in col_info
            if "VARCHAR" in row[1].upper() or "CHAR" in row[1].upper()
        ]
        if not varchar_cols:
            return 0

        total = 0
        for col in varchar_cols:
            try:
                non_null, numeric = self._conn.execute(f"""
                    SELECT
                        COUNT(*) FILTER (WHERE {col} IS NOT NULL),
                        COUNT(*) FILTER (WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL)
                    FROM (SELECT {col} FROM {name} LIMIT 1000)
                """).fetchone()
            except Exception:
                continue

            if non_null == 0 or numeric == 0 or numeric >= non_null * 0.5:
                continue

            try:
                rows = self._conn.execute(f"""
                    SELECT rn, val FROM (
                        SELECT ROW_NUMBER() OVER () AS rn, {col} AS val
                        FROM {name} LIMIT 1000
                    ) WHERE TRY_CAST(val AS DOUBLE) IS NOT NULL
                """).fetchall()
            except Exception:
                continue

            if not rows:
                continue

            self._ensure_errors_table(name)
            for rn, val in rows:
                self._conn.execute(
                    f"INSERT INTO _errors_{name} VALUES (?, NULL, 'type_anomaly', ?, ?)",
                    [rn, col, f"column {col}: expected non-numeric, got {val!r}"],
                )
            total += len(rows)

        return total

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def has_errors(self, name: str) -> bool:
        return self.get(name).error_count > 0

    def get_error_count(self, name: str) -> int:
        return self.get(name).error_count

    def get_warnings(self, name: str) -> list[str]:
        return self._warnings.get(name, [])

    def rename_column(self, name: str, old_col: str, new_col: str) -> None:
        entry = self.get(name)
        _validate_name(new_col)

        cols = [row[0] for row in self._conn.execute(f"DESCRIBE {name}").fetchall()]
        if old_col not in cols:
            raise CatalogError(f"Column '{old_col}' not found in table '{name}'.")
        if new_col in cols and new_col != old_col:
            raise CatalogError(f"Column '{new_col}' already exists in table '{name}'.")

        select_list = ", ".join(
            f'"{c}" AS "{new_col}"' if c == old_col else f'"{c}"'
            for c in cols
        )
        read_fn = _read_function(entry.format, entry.path)
        self._conn.execute(
            f"CREATE OR REPLACE VIEW {name} AS SELECT {select_list} FROM {read_fn}"
        )