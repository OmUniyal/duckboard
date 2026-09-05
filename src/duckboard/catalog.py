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
    delimiter: str | None = None  # None = format default
    quotechar: str | None = None  # None = format default (")


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
    delimiter: str | None = None,
    quotechar: str | None = None,
) -> str:
    """Return DuckDB read_* SQL for a file path."""
    path_literal = str(path.resolve()).replace("\\", "/").replace("'", "''")
    extras = _header_clause(no_header, column_names)
    if fmt in ("csv", "psv"):
        extra_parts: list[str] = []
        # Delimiter: use explicit value, else PSV default, else let DuckDB auto-detect
        if delimiter is not None:
            extra_parts.append(f"sep='{delimiter.replace(chr(39), chr(39)*2)}'")
        elif fmt == "psv":
            extra_parts.append("sep='|'")
        if quotechar is not None:
            extra_parts.append(f"quote='{quotechar.replace(chr(39), chr(39)*2)}'")
        sep_str = (", " + ", ".join(extra_parts)) if extra_parts else ""
        return f"read_csv_auto('{path_literal}', ignore_errors=true{sep_str}{extras})"
    if fmt == "parquet":
        return f"read_parquet('{path_literal}')"
    if fmt == "json":
        # JSONL/NDJSON: tolerate malformed lines so Python scan can capture them
        if path.suffix.lower() in (".jsonl", ".ndjson"):
            return f"read_json_auto('{path_literal}', ignore_errors=true)"
        return f"read_json_auto('{path_literal}')"
    raise CatalogError(f"Unknown format: {fmt}")


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
        delimiter: str | None = None,
        quotechar: str | None = None,
    ) -> CatalogEntry:
        _validate_name(name)

        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise CatalogError(f"File not found: {resolved}")

        fmt = _detect_format(resolved)

        if delimiter is not None and fmt not in ("csv", "psv"):
            raise CatalogError(
                f"--delimiter is not applicable to {fmt.upper()} files."
            )
        if quotechar is not None and fmt not in ("csv", "psv"):
            raise CatalogError(
                f"--quotechar is not applicable to {fmt.upper()} files."
            )

        # Auto-infer tab delimiter for .tsv files
        if delimiter is None and resolved.suffix.lower() == ".tsv":
            delimiter = "\t"

        read_fn = _read_function(
            fmt, resolved,
            no_header=no_header, column_names=column_names,
            delimiter=delimiter, quotechar=quotechar,
        )

        try:
            self._conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {read_fn}")
        except Exception as exc:
            if fmt == "json":
                raise CatalogError(
                    f"Could not load '{resolved.name}' as tabular JSON. "
                    "Expected a JSON array of objects or newline-delimited JSON records. "
                    f"DuckDB: {exc}"
                ) from exc
            raise CatalogError(str(exc)) from exc

        # Post-load non-tabular JSON guard (DuckDB doesn't raise on scalars/objects)
        if fmt == "json" and resolved.suffix.lower() == ".json":
            self._check_json_tabular(name, resolved)

        self._warnings[name] = []
        error_count = 0

        if fmt in ("csv", "psv"):
            if not no_header and self._no_header_heuristic(name):
                self._warnings[name].append(
                    f"Warning: first row of '{name}' may be data, not headers. "
                    "Use ':load ... --no-header' if needed."
                )
            error_count += self._run_structural_validation(
                name, resolved, fmt, delimiter=delimiter, quotechar=quotechar
            )
            error_count += self._run_type_anomaly_detection(name)

        if fmt == "json" and resolved.suffix.lower() in (".jsonl", ".ndjson"):
            error_count += self._run_jsonl_validation(name, resolved)

        if fmt == "json":
            self._run_json_schema_check(name)

        self._run_all_null_check(name)

        entry = CatalogEntry(
            name=name, path=resolved, format=fmt, error_count=error_count,
            delimiter=delimiter, quotechar=quotechar,
        )
        self._entries[name] = entry
        self._run_row_count_crosscheck(name, resolved, fmt, error_count)
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

    def _run_structural_validation(
        self,
        name: str,
        path: Path,
        fmt: str,
        delimiter: str | None = None,
        quotechar: str | None = None,
    ) -> int:
        import csv as _csv

        sep = delimiter if delimiter is not None else ("|" if fmt == "psv" else ",")

        # Python csv.reader only supports single-char delimiters.
        # Multi-char delimiters fall back to DuckDB + residual cross-check only.
        if len(sep) > 1:
            return 0

        errors: list[tuple[int, str, str]] = []
        reader_kwargs: dict = {"delimiter": sep}
        if quotechar is not None:
            reader_kwargs["quotechar"] = quotechar

        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as fh:
                reader = _csv.reader(fh, **reader_kwargs)
                try:
                    header = next(reader)
                except StopIteration:
                    return 0
                expected = len(header)

                for i, row in enumerate(reader, start=2):
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

    def _run_row_count_crosscheck(
        self,
        name: str,
        path: Path,
        fmt: str,
        error_count: int,
    ) -> None:
        """Compare raw file row count against DuckDB-loaded count.

        Any shortfall beyond what Python validation already caught is stored
        as a warning with exact numbers so the root cause can be diagnosed.
        """
        try:
            loaded_count: int = self._conn.execute(
                f"SELECT COUNT(*) FROM {name}"
            ).fetchone()[0]
        except Exception:
            return

        raw_count: int | None = None

        if fmt in ("csv", "psv"):
            try:
                with path.open("rb") as fh:
                    raw_count = sum(1 for _ in fh) - 1  # subtract header line
            except Exception:
                return
        else:
            reader_fn = "read_parquet" if fmt == "parquet" else "read_json_auto"
            path_literal = str(path.resolve()).replace("\\", "/").replace("'", "''")
            try:
                raw_count = self._conn.execute(
                    f"SELECT COUNT(*) FROM {reader_fn}('{path_literal}')"
                ).fetchone()[0]
            except Exception:
                return  # DuckDB itself threw — can't determine raw count

        if raw_count is None:
            return

        residual = max(0, raw_count - loaded_count - error_count)
        if residual > 0:
            self._warnings[name].append(
                f"{residual} row(s) were dropped by DuckDB but not captured in "
                f"the error table (cause unknown — may be encoding, embedded "
                f"nulls, or a DuckDB type coercion issue). "
                f"Raw line count: {raw_count}, loaded: {loaded_count}, "
                f"known errors: {error_count}."
            )

    def _run_all_null_check(self, name: str) -> None:
        """Warn for any column where every value is NULL."""
        try:
            col_info = self._conn.execute(f"DESCRIBE {name}").fetchall()
        except Exception:
            return
        for row in col_info:
            col = row[0]
            try:
                count = self._conn.execute(
                    f'SELECT COUNT(*) FROM {name} WHERE "{col}" IS NOT NULL'
                ).fetchone()[0]
            except Exception:
                continue
            if count == 0:
                self._warnings[name].append(
                    f"Warning: column '{col}' has no non-null values (all NULL)."
                )

    def _run_jsonl_validation(self, name: str, path: Path) -> int:
        """Scan every line of a JSONL/NDJSON file with json.loads().

        Captures malformed lines in _errors_{name} as error_type='json_parse'.
        Prints a progress note to stdout for files larger than 50 MB.
        """
        import json as _json

        _LARGE_FILE_BYTES = 50 * 1024 * 1024  # 50 MB

        try:
            file_size = path.stat().st_size
        except Exception:
            file_size = 0

        if file_size > _LARGE_FILE_BYTES:
            size_mb = file_size / (1024 * 1024)
            print(f"  Scanning {size_mb:.1f} MB JSONL file for malformed lines...")

        errors: list[tuple[int, str, str]] = []

        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        _json.loads(stripped)
                    except _json.JSONDecodeError as exc:
                        errors.append((i, stripped[:200], str(exc)))
        except Exception:
            return 0

        if not errors:
            return 0

        self._ensure_errors_table(name)
        for row_number, raw_line, reason in errors:
            self._conn.execute(
                f"INSERT INTO _errors_{name} VALUES (?, ?, 'json_parse', NULL, ?)",
                [row_number, raw_line, reason],
            )
        return len(errors)

    def _run_json_schema_check(self, name: str) -> None:
        """Warn for any column DuckDB inferred as JSON type (mixed structure)."""
        try:
            col_info = self._conn.execute(f"DESCRIBE {name}").fetchall()
        except Exception:
            return
        for row in col_info:
            col_name, col_type = row[0], row[1]
            if col_type.upper() == "JSON":
                self._warnings[name].append(
                    f"Warning: column '{col_name}' was inferred as JSON type — "
                    "values have inconsistent structure across records."
                )

    def _check_json_tabular(self, name: str, path: Path) -> None:
        """Raise CatalogError if a .json file did not load as a proper table."""
        try:
            cols = self._conn.execute(f"DESCRIBE {name}").fetchall()
        except Exception:
            return

        if not cols:
            self._conn.execute(f"DROP VIEW IF EXISTS {name}")
            raise CatalogError(
                f"Could not load '{path.name}' as tabular JSON. "
                "Expected a JSON array of objects."
            )

        # DuckDB names the column 'json' when loading a scalar or array of
        # scalars — these are not valid tabular data.
        col_names = [r[0].lower() for r in cols]
        if col_names == ["json"]:
            self._conn.execute(f"DROP VIEW IF EXISTS {name}")
            raise CatalogError(
                f"Could not load '{path.name}' as tabular JSON. "
                "Expected a JSON array of objects (got a scalar or array of scalars)."
            )

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
        read_fn = _read_function(
            entry.format, entry.path,
            delimiter=entry.delimiter, quotechar=entry.quotechar,
        )
        self._conn.execute(
            f"CREATE OR REPLACE VIEW {name} AS SELECT {select_list} FROM {read_fn}"
        )