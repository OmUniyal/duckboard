"""File catalog — register paths as queryable table/view names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

from duckboard.exceptions import CatalogError

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_CSV_EXTENSIONS = {".csv", ".tsv"}
_PARQUET_EXTENSIONS = {".parquet"}
_JSON_EXTENSIONS = {".json", ".jsonl", ".ndjson"}


@dataclass(frozen=True)
class CatalogEntry:
    """One registered file."""

    name: str
    path: Path
    format: str  # "csv", "parquet", or "json"


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
    if ext in _PARQUET_EXTENSIONS:
        return "parquet"
    if ext in _JSON_EXTENSIONS:
        return "json"
    raise CatalogError(
        f"Unsupported file type {ext!r} for {path}. "
        "Supported: .csv, .tsv, .parquet, .json, .jsonl, .ndjson"
    )


def _read_function(fmt: str, path: Path) -> str:
    """Return DuckDB read_* SQL for a file path."""
    # Forward slashes keep Windows paths safe inside SQL string literals.
    path_literal = str(path.resolve()).replace("\\", "/").replace("'", "''")
    if fmt == "csv":
        return f"read_csv_auto('{path_literal}')"
    if fmt == "parquet":
        return f"read_parquet('{path_literal}')"
    if fmt == "json":
        return f"read_json_auto('{path_literal}')"
    raise CatalogError(f"Unknown format: {fmt}")


class FileCatalog:
    """Register files as DuckDB views queryable by name."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._entries: dict[str, CatalogEntry] = {}

    def load(self, name: str, path: str | Path) -> CatalogEntry:
        _validate_name(name)

        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise CatalogError(f"File not found: {resolved}")

        fmt = _detect_format(resolved)
        read_fn = _read_function(fmt, resolved)

        self._conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {read_fn}")

        entry = CatalogEntry(name=name, path=resolved, format=fmt)
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
        del self._entries[name]