"""Tests for catalog validation — structural and type anomaly detection."""

from __future__ import annotations

import duckdb
import pytest

from duckboard.catalog import FileCatalog
from duckboard.session import DuckboardSession


def _catalog():
    conn = duckdb.connect()
    return FileCatalog(conn)


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def test_structural_error_caught(tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("a,b,c\n1,2,3\n4,5,6,7\n")  # row 3 has 4 fields
    cat = _catalog()
    entry = cat.load("bad", csv)
    assert entry.error_count == 1
    rows = cat._conn.execute("SELECT * FROM _errors_bad").fetchall()
    assert rows[0][2] == "structural"
    assert "column count mismatch" in rows[0][4]


def test_clean_file_has_no_errors(tmp_path):
    csv = tmp_path / "clean.csv"
    csv.write_text("a,b,c\n1,2,3\n4,5,6\n")
    cat = _catalog()
    entry = cat.load("clean", csv)
    assert entry.error_count == 0
    assert not cat.has_errors("clean")


def test_structural_error_row_number(tmp_path):
    csv = tmp_path / "rn.csv"
    csv.write_text("x,y\n1,2\n3,4\nbad\n6,7\n")  # row 4 has 1 field
    cat = _catalog()
    entry = cat.load("rn", csv)
    assert entry.error_count == 1
    row = cat._conn.execute("SELECT row_number FROM _errors_rn").fetchone()
    assert row[0] == 4


def test_multiple_structural_errors(tmp_path):
    csv = tmp_path / "multi.csv"
    csv.write_text("a,b\n1,2\nbad\n4,5,6\n7,8\n")  # rows 3 and 4 are bad
    cat = _catalog()
    entry = cat.load("multi", csv)
    assert entry.error_count == 2


# ---------------------------------------------------------------------------
# Type anomaly detection
# ---------------------------------------------------------------------------

def test_type_anomaly_caught(tmp_path):
    csv = tmp_path / "anomaly.csv"
    csv.write_text("name,gender,score\nAlice,F,95\nBob,M,87\nCarol,42,91\nDave,M,78\n")
    cat = _catalog()
    entry = cat.load("anomaly", csv)
    assert entry.error_count == 1
    rows = cat._conn.execute("SELECT * FROM _errors_anomaly").fetchall()
    assert rows[0][2] == "type_anomaly"
    assert rows[0][3] == "gender"


def test_numeric_column_not_flagged(tmp_path):
    csv = tmp_path / "numeric.csv"
    csv.write_text("id,score\n1,95\n2,87\n3,91\n")
    cat = _catalog()
    entry = cat.load("numeric", csv)
    assert entry.error_count == 0


def test_mixed_errors_count(tmp_path):
    csv = tmp_path / "mixed.csv"
    # row 2: structural (4 fields vs 3); row 4: type anomaly in gender
    csv.write_text("name,gender,score\nAlice,F,95,extra\nBob,M,87\nCarol,42,91\n")
    cat = _catalog()
    entry = cat.load("mixed", csv)
    assert entry.error_count == 1  # structural only; type anomaly threshold not met with 2 rows


# ---------------------------------------------------------------------------
# Unload clears errors table
# ---------------------------------------------------------------------------

def test_unload_drops_errors_table(tmp_path):
    csv = tmp_path / "bad2.csv"
    csv.write_text("a,b\n1,2\nbad\n")
    cat = _catalog()
    cat.load("bad2", csv)
    cat.unload("bad2")
    exists = cat._conn.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '_errors_bad2'
    """).fetchone()[0]
    assert exists == 0


# ---------------------------------------------------------------------------
# get_error_count and get_warnings
# ---------------------------------------------------------------------------

def test_get_error_count(tmp_path):
    csv = tmp_path / "ec.csv"
    csv.write_text("a,b\n1,2\nbad\n")
    cat = _catalog()
    cat.load("ec", csv)
    assert cat.get_error_count("ec") == 1


def test_get_warnings_clean_file(tmp_path):
    csv = tmp_path / "warn.csv"
    csv.write_text("id,name\n1,Alice\n2,Bob\n")
    cat = _catalog()
    cat.load("warn", csv)
    assert cat.get_warnings("warn") == []