"""End-to-end smoke test — exercises the full happy path without mocks."""

from __future__ import annotations

from pathlib import Path

import pytest

from duckboard.session import DuckboardSession
from duckboard.formatter import format_table
from duckboard.commands import handle_command

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SAMPLE_CSV = EXAMPLES / "sample.csv"


def test_smoke_load_query_save_unload(tmp_path):
    """Full happy path: load → query → format → save → unload."""
    with DuckboardSession() as session:
        # 1. Load
        entry = session.load("sample", SAMPLE_CSV)
        assert entry.name == "sample"
        assert entry.format == "csv"

        # 2. Query
        cols, rows = session.fetch(
            "SELECT color, COUNT(*) AS n FROM sample GROUP BY 1 ORDER BY 1"
        )
        assert cols == ["color", "n"]
        assert ("red", 2) in rows
        assert ("blue", 1) in rows

        # 3. Format — box renders without error
        out = format_table(cols, rows)
        assert "┌" in out
        assert "color" in out
        assert "red" in out
        assert "(3 rows)" in out

        # 4. Save via command
        out_csv = tmp_path / "results.csv"
        last_result = (cols, rows)
        result = handle_command(
            f":save {str(out_csv).replace(chr(92), '/')}",
            session,
            last_result=last_result,
        )
        assert "Saved" in result
        assert out_csv.exists()

        # 5. Schema
        schema_cols, schema_rows = session.schema("sample")
        assert schema_cols == ["column", "type", "nullable"]
        assert any(r[0] == "color" for r in schema_rows)

        # 6. Tables list
        entries = session.catalog.list_tables()
        assert any(e.name == "sample" for e in entries)

        # 7. Unload
        session.unload("sample")
        entries = session.catalog.list_tables()
        assert not any(e.name == "sample" for e in entries)