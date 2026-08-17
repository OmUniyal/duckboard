"""DuckboardSession — core engine; everything else wraps this."""

from __future__ import annotations

from pathlib import Path

import duckdb

from duckboard.catalog import CatalogEntry, FileCatalog


class DuckboardSession:
    """Owns a DuckDB connection and session state for file-first querying."""

    def __init__(self) -> None:
        self._conn = duckdb.connect()
        self.catalog = FileCatalog(self._conn)

    def load(self, name: str, path: str | Path) -> CatalogEntry:
        """Register a file as a queryable table name."""
        return self.catalog.load(name, path)

    def execute(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Run SQL and return the DuckDB relation."""
        return self._conn.execute(sql)

    def fetch(self, sql: str) -> tuple[list[str], list[tuple]]:
        rel = self.execute(sql)
        return rel.columns, rel.fetchall()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DuckboardSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()