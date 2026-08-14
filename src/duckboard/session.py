"""DuckboardSession — core engine; everything else wraps this."""

from __future__ import annotations

import duckdb


class DuckboardSession:
    """Owns a DuckDB connection and session state for file-first querying."""

    def __init__(self) -> None:
        self._conn = duckdb.connect()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DuckboardSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
