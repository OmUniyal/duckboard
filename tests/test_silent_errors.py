"""Tests for full-file validation and residual row-count cross-check."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from duckboard.catalog import FileCatalog
from duckboard.session import DuckboardSession


# ── Full-file validation (1,000-row cap removed) ──────────────────────────────

def test_full_scan_catches_row_beyond_1000(tmp_path):
    """Structural error at row 1,050 must appear in _errors_ table."""
    csv_file = tmp_path / "big.csv"
    lines = ["id,value\n"]
    for i in range(1, 1101):
        if i == 1050:
            lines.append(f"{i},oops,extra\n")  # wrong column count
        else:
            lines.append(f"{i},normal\n")
    csv_file.write_text("".join(lines))

    with DuckboardSession() as session:
        entry = session.load("big", str(csv_file))
        assert entry.error_count >= 1
        assert session.get_error_count("big") >= 1


def test_clean_file_no_warnings(tmp_path):
    csv_file = tmp_path / "clean.csv"
    csv_file.write_text("id,name\n1,alice\n2,bob\n")

    with DuckboardSession() as session:
        session.load("clean", str(csv_file))
        assert session.get_warnings("clean") == []
        assert session.get_error_count("clean") == 0


# ── Residual cross-check unit tests (mock connection) ────────────────────────

def _catalog_with_mock_conn() -> tuple[MagicMock, FileCatalog]:
    """Return (mock_conn, catalog) — mock conn avoids C-extension patching."""
    conn = MagicMock()
    return conn, FileCatalog(conn)


def test_residual_drop_generates_warning(tmp_path):
    """loaded < raw → warning with exact counts in message."""
    csv_file = tmp_path / "test.csv"
    # 5 data rows + 1 header = 6 lines → raw_count = 5
    csv_file.write_text("id,name\n1,a\n2,b\n3,c\n4,d\n5,e\n")

    conn, catalog = _catalog_with_mock_conn()
    conn.execute.return_value.fetchone.return_value = (3,)  # loaded_count = 3
    catalog._warnings["test"] = []

    catalog._run_row_count_crosscheck("test", csv_file, "csv", 0)

    warnings = catalog._warnings["test"]
    assert len(warnings) == 1
    assert "2 row(s)" in warnings[0]
    assert "Raw line count: 5" in warnings[0]
    assert "loaded: 3" in warnings[0]
    assert "known errors: 0" in warnings[0]


def test_residual_accounts_for_known_errors(tmp_path):
    """known error_count is subtracted before computing residual."""
    csv_file = tmp_path / "test.csv"
    # 10 data rows + 1 header → raw_count = 10
    csv_file.write_text("id,name\n" + "".join(f"{i},x\n" for i in range(10)))

    conn, catalog = _catalog_with_mock_conn()
    conn.execute.return_value.fetchone.return_value = (7,)  # loaded = 7
    catalog._warnings["test"] = []

    # error_count=2 already known; residual = 10 - 7 - 2 = 1
    catalog._run_row_count_crosscheck("test", csv_file, "csv", 2)

    warnings = catalog._warnings["test"]
    assert len(warnings) == 1
    assert "1 row(s)" in warnings[0]


def test_no_warning_when_counts_balance(tmp_path):
    """No warning when loaded + known errors == raw count."""
    csv_file = tmp_path / "test.csv"
    # 3 data rows + 1 header → raw_count = 3
    csv_file.write_text("id,name\n1,a\n2,b\n3,c\n")

    conn, catalog = _catalog_with_mock_conn()
    conn.execute.return_value.fetchone.return_value = (2,)  # loaded = 2
    catalog._warnings["test"] = []

    # error_count=1; residual = 3 - 2 - 1 = 0
    catalog._run_row_count_crosscheck("test", csv_file, "csv", 1)

    assert catalog._warnings["test"] == []


def test_parquet_raw_count_throws_skips_check(tmp_path):
    """If the raw-count DuckDB query throws, no crash and no warning."""
    fake_parquet = tmp_path / "broken.parquet"
    fake_parquet.write_bytes(b"not a parquet file")

    conn, catalog = _catalog_with_mock_conn()
    catalog._warnings["broken"] = []

    call_count = [0]

    def side_effect(sql, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:          # COUNT(*) FROM view → success
            m = MagicMock()
            m.fetchone.return_value = (5,)
            return m
        raise Exception("not a parquet file")   # raw count query → throws

    conn.execute.side_effect = side_effect

    catalog._run_row_count_crosscheck("broken", fake_parquet, "parquet", 0)

    assert catalog._warnings["broken"] == []


def test_count_query_throws_skips_check(tmp_path):
    """If the initial COUNT(*) FROM view fails, whole check is skipped."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id\n1\n2\n")

    conn, catalog = _catalog_with_mock_conn()
    conn.execute.side_effect = Exception("view gone")
    catalog._warnings["test"] = []

    catalog._run_row_count_crosscheck("test", csv_file, "csv", 0)

    assert catalog._warnings["test"] == []