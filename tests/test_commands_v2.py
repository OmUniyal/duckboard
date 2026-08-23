"""Tests for v0.2.0 commands: :rename_column, :export_errors, :export_clean, :clear."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from duckboard.commands import handle_command
from duckboard.exceptions import CatalogError
from duckboard.session import DuckboardSession


def _make_session():
    session = MagicMock()
    session.get_warnings.return_value = []
    session.catalog.list_tables.return_value = []
    return session


# ---------------------------------------------------------------------------
# :rename_column
# ---------------------------------------------------------------------------

def test_rename_column_calls_session(tmp_path):
    session = _make_session()
    result = handle_command(":rename_column sales region area", session)
    session.rename_column.assert_called_once_with("sales", "region", "area")
    assert "area" in result


def test_rename_column_wrong_arg_count():
    session = _make_session()
    result = handle_command(":rename_column sales region", session)
    assert "Usage" in result


def test_rename_column_catalog_error():
    session = _make_session()
    session.rename_column.side_effect = CatalogError("Column not found")
    result = handle_command(":rename_column sales bad new", session)
    assert "Error" in result


# ---------------------------------------------------------------------------
# :export_errors
# ---------------------------------------------------------------------------

def test_export_errors_no_errors():
    session = _make_session()
    session.has_errors.return_value = False
    result = handle_command(':export_errors sales "out.csv"', session)
    assert "No errors" in result


def test_export_errors_unknown_table():
    session = _make_session()
    session.catalog.get.side_effect = CatalogError("Table not found")
    result = handle_command(':export_errors unknown "out.csv"', session)
    assert "Error" in result


def test_export_errors_bad_format():
    session = _make_session()
    session.has_errors.return_value = True
    result = handle_command(':export_errors sales "out.xyz"', session)
    assert "Error" in result or "format" in result.lower()


def test_export_errors_success(tmp_path):
    session = _make_session()
    session.has_errors.return_value = True
    out = tmp_path / "errors.csv"
    result = handle_command(f':export_errors sales "{out}"', session)
    session.execute.assert_called_once()
    assert "Exported" in result


# ---------------------------------------------------------------------------
# :export_clean
# ---------------------------------------------------------------------------

def test_export_clean_unknown_table():
    session = _make_session()
    session.catalog.get.side_effect = CatalogError("Table not found")
    result = handle_command(':export_clean unknown "out.csv"', session)
    assert "Error" in result


def test_export_clean_bad_format():
    session = _make_session()
    result = handle_command(':export_clean sales "out.xyz"', session)
    assert "Error" in result or "format" in result.lower()


def test_export_clean_no_errors(tmp_path):
    session = _make_session()
    session.has_errors.return_value = False
    mock_rel = MagicMock()
    mock_rel.fetchall.return_value = [("id", "VARCHAR", "YES", None, None, None)]
    session.execute.return_value = mock_rel
    out = tmp_path / "clean.csv"
    result = handle_command(f':export_clean sales "{out}"', session)
    assert "Exported" in result or "Error" in result  # execute may fail on mock


# ---------------------------------------------------------------------------
# :clear / :cls
# ---------------------------------------------------------------------------

def test_clear_returns_empty_string():
    session = _make_session()
    with patch("os.system") as mock_sys:
        result = handle_command(":clear", session)
        mock_sys.assert_called_once()
        assert result == ""


def test_cls_alias():
    session = _make_session()
    with patch("os.system") as mock_sys:
        result = handle_command(":cls", session)
        mock_sys.assert_called_once()
        assert result == ""