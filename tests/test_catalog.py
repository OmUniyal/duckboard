"""Tests for file catalog and session.load()."""

import json
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


# ---------------------------------------------------------------------------
# Parquet
# ---------------------------------------------------------------------------

def test_load_parquet_and_query(tmp_path):
    import duckdb
    pq = tmp_path / "colors.parquet"
    conn = duckdb.connect()
    conn.execute("CREATE TABLE _tmp AS SELECT 'red' AS color, 1 AS n")
    conn.execute(f"COPY _tmp TO '{str(pq).replace(chr(92), '/')}' (FORMAT PARQUET)")
    conn.close()

    with DuckboardSession() as session:
        session.load("colors", pq)
        cols, rows = session.fetch("SELECT color FROM colors")
    assert cols == ["color"]
    assert ("red",) in rows


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def test_load_json_and_query(tmp_path):
    jf = tmp_path / "items.json"
    jf.write_text(json.dumps([{"item": "apple", "qty": 3}, {"item": "banana", "qty": 5}]))

    with DuckboardSession() as session:
        session.load("items", jf)
        cols, rows = session.fetch("SELECT item FROM items ORDER BY item")
    assert "item" in cols
    assert ("apple",) in rows


# ---------------------------------------------------------------------------
# PSV
# ---------------------------------------------------------------------------

def test_load_psv_and_query(tmp_path):
    psv = tmp_path / "data.psv"
    psv.write_text("color|n\nred|1\nblue|2\n")

    with DuckboardSession() as session:
        session.load("data", psv)
        cols, rows = session.fetch("SELECT color FROM data ORDER BY color")
    assert "color" in cols
    assert ("blue",) in rows


# ---------------------------------------------------------------------------
# list_tables
# ---------------------------------------------------------------------------

def test_list_tables_returns_sorted(tmp_path):
    csv1 = tmp_path / "aaa.csv"
    csv2 = tmp_path / "zzz.csv"
    csv1.write_text("x\n1\n")
    csv2.write_text("x\n2\n")

    with DuckboardSession() as session:
        session.load("zzz", csv2)
        session.load("aaa", csv1)
        entries = session.catalog.list_tables()
    assert [e.name for e in entries] == ["aaa", "zzz"]


def test_list_tables_empty():
    with DuckboardSession() as session:
        assert session.catalog.list_tables() == []


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_returns_entry(tmp_path):
    csv = tmp_path / "sample.csv"
    csv.write_text("a\n1\n")

    with DuckboardSession() as session:
        session.load("sample", csv)
        entry = session.catalog.get("sample")
    assert entry.name == "sample"
    assert entry.format == "csv"


def test_get_unknown_raises(tmp_path):
    with DuckboardSession() as session:
        with pytest.raises(CatalogError):
            session.catalog.get("ghost")