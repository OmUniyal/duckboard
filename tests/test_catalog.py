"""Tests for file catalog and session.load()."""

from pathlib import Path

import pytest

from duckboard import DuckboardSession
from duckboard.exceptions import CatalogError

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SAMPLE_CSV = EXAMPLES / "sample.csv"


def test_load_csv_and_query() -> None:
    with DuckboardSession() as session:
        entry = session.load("sample", SAMPLE_CSV)

        assert entry.name == "sample"
        assert entry.format == "csv"
        assert entry.path == SAMPLE_CSV.resolve()

        result = session.execute(
            "SELECT color, COUNT(*) AS n FROM sample GROUP BY 1 ORDER BY 1"
        ).fetchall()

        assert result == [("blue", 1), ("green", 1), ("red", 2)]


def test_load_missing_file_raises() -> None:
    with DuckboardSession() as session:
        with pytest.raises(CatalogError, match="File not found"):
            session.load("sample", EXAMPLES / "nope.csv")


def test_invalid_table_name_raises() -> None:
    with DuckboardSession() as session:
        with pytest.raises(CatalogError, match="Invalid table name"):
            session.load("2bad", SAMPLE_CSV)


def test_unknown_extension_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "data.xyz"
    bad_file.write_text("hello", encoding="utf-8")

    with DuckboardSession() as session:
        with pytest.raises(CatalogError, match="Unsupported file type"):
            session.load("data", bad_file)


def test_reload_replaces_view() -> None:
    with DuckboardSession() as session:
        session.load("sample", SAMPLE_CSV)
        session.load("sample", SAMPLE_CSV)  # should not error

        count = session.execute("SELECT COUNT(*) FROM sample").fetchone()
        assert count == (4,)