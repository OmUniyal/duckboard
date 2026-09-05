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

    def load(
        self,
        name: str,
        path: str | Path,
        no_header: bool = False,
        column_names: list[str] | None = None,
        delimiter: str | None = None,
        quotechar: str | None = None,
    ) -> CatalogEntry:
        return self.catalog.load(
            name, path,
            no_header=no_header, column_names=column_names,
            delimiter=delimiter, quotechar=quotechar,
        )

    def execute(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Run SQL and return the DuckDB relation."""
        return self._conn.sql(sql)

    def fetch(self, sql: str) -> tuple[list[str], list[tuple]]:
        rel = self.execute(sql)
        return rel.columns, rel.fetchall()

    def unload(self, name: str) -> None:
        self.catalog.unload(name)

    def schema(self, name: str) -> tuple[list[str], list[tuple]]:
        entry = self.catalog.get(name)  # raises CatalogError if not found
        rel = self.execute(f"DESCRIBE {entry.name}")
        rows = rel.fetchall()
        # DESCRIBE returns: column_name, column_type, null, key, default, extra
        columns = ["column", "type", "nullable"]
        data = [
            (row[0], row[1], str(row[2] == "YES"))
            for row in rows
        ]
        return columns, data

    def get_warnings(self, name: str) -> list[str]:
        """Return heuristic warnings for a loaded table."""
        return self.catalog.get_warnings(name)

    def get_error_count(self, name: str) -> int:
        """Return validation error count for a loaded table."""
        return self.catalog.get_error_count(name)

    def has_errors(self, name: str) -> bool:
        """Return True if the table has any validation errors."""
        return self.catalog.has_errors(name)

    def rename_column(self, name: str, old_col: str, new_col: str) -> None:
        """Rename a column in a loaded table."""
        self.catalog.rename_column(name, old_col, new_col)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DuckboardSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()