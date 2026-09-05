from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from duckboard.commands import handle_command
from duckboard.exceptions import CatalogError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(load_return=None, schema_return=None, tables_return=None):
    session = MagicMock()
    session.get_warnings.return_value = []
    if load_return:
        session.load.return_value = load_return
    if schema_return:
        session.schema.return_value = schema_return
    if tables_return:
        session.catalog.list_tables.return_value = tables_return
    else:
        session.catalog.list_tables.return_value = []
    return session


def _mock_entry(name="sample", fmt="csv", path="/data/sample.csv"):
    entry = MagicMock()
    entry.name = name
    entry.format = fmt
    entry.path = Path(path)
    entry.error_count = 0
    return entry


# ---------------------------------------------------------------------------
# :load
# ---------------------------------------------------------------------------

def test_load_defaults_name_to_stem(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("a,b\n1,2\n")
    entry = _mock_entry(name="sales", fmt="csv", path=str(csv))
    session = _make_session(load_return=entry)
    result = handle_command(f":load {csv}", session)
    session.load.assert_called_once_with("sales", str(csv).replace("\\", "/"), no_header=False, column_names=None, delimiter=None, quotechar=None)
    assert "sales" in result


def test_load_uses_as_name(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("a,b\n1,2\n")
    entry = _mock_entry(name="revenue", fmt="csv", path=str(csv))
    session = _make_session(load_return=entry)
    result = handle_command(f':load "{csv}" as revenue', session)
    session.load.assert_called_once_with("revenue", str(csv).replace("\\", "/"), no_header=False, column_names=None, delimiter=None, quotechar=None)
    assert "revenue" in result


def test_load_missing_file_returns_error():
    session = _make_session()
    session.load.side_effect = CatalogError("File not found")
    result = handle_command(":load /no/such/file.csv", session)
    assert "Error" in result


# ---------------------------------------------------------------------------
# :tables
# ---------------------------------------------------------------------------

def test_tables_box_output():
    entry = _mock_entry()
    session = _make_session(tables_return=[entry])
    result = handle_command(":tables", session)
    assert "name" in result
    assert "sample" in result


def test_tables_empty():
    session = _make_session(tables_return=[])
    result = handle_command(":tables", session)
    assert "no tables" in result


# ---------------------------------------------------------------------------
# :schema
# ---------------------------------------------------------------------------

def test_schema_returns_box():
    session = _make_session(
        schema_return=(
            ["column", "type", "nullable"],
            [("color", "VARCHAR", "True"), ("n", "BIGINT", "False")],
        )
    )
    result = handle_command(":schema sample", session)
    assert "column" in result
    assert "VARCHAR" in result


def test_schema_unknown_table_returns_error():
    session = _make_session()
    session.schema.side_effect = CatalogError("No table named 'ghost'")
    result = handle_command(":schema ghost", session)
    assert "Error" in result


# ---------------------------------------------------------------------------
# :save
# ---------------------------------------------------------------------------

def test_save_no_prior_result():
    session = _make_session()
    result = handle_command(":save output.csv", session, last_result=None)
    assert "No query result" in result


def test_save_csv(tmp_path):
    out = tmp_path / "output.csv"
    out_str = str(out).replace("\\", "/")
    last = (["color", "n"], [("red", 2), ("blue", 1)])
    session = _make_session()
    result = handle_command(f":save {out_str}", session, last_result=last)
    assert "Saved" in result
    assert out.exists()


def test_save_explicit_format_override(tmp_path):
    out = tmp_path / "output.dat"
    out_str = str(out).replace("\\", "/")
    last = (["color", "n"], [("red", 2), ("blue", 1)])
    session = _make_session()
    result = handle_command(f":save {out_str} --csv", session, last_result=last)
    assert "Saved" in result
    assert out.exists()


# ---------------------------------------------------------------------------
# :unload
# ---------------------------------------------------------------------------

def test_unload_removes_table():
    session = _make_session()
    result = handle_command(":unload sample", session)
    session.unload.assert_called_once_with("sample")
    assert "Unloaded" in result


def test_unload_unknown_table_returns_error():
    session = _make_session()
    session.unload.side_effect = CatalogError("No table named 'ghost'")
    result = handle_command(":unload ghost", session)
    assert "Error" in result


# ---------------------------------------------------------------------------
# :pwd
# ---------------------------------------------------------------------------

def test_pwd_returns_cwd():
    session = _make_session()
    result = handle_command(":pwd", session)
    assert result == os.getcwd()


# ---------------------------------------------------------------------------
# Unknown command
# ---------------------------------------------------------------------------

def test_unknown_command():
    session = _make_session()
    result = handle_command(":blorp", session)
    assert "Unknown command" in result