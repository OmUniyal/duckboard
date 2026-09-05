"""Tests for v0.4.0 :load flag extensions and :schema delimiter output."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from duckboard.commands import handle_command, _parse_load
from duckboard.exceptions import CatalogError


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_commands.py)
# ---------------------------------------------------------------------------

def _make_session(load_return=None):
    session = MagicMock()
    session.get_warnings.return_value = []
    if load_return:
        session.load.return_value = load_return
    session.catalog.list_tables.return_value = []
    return session


def _mock_entry(name="sample", fmt="csv", path="/data/sample.csv",
                delimiter=None, quotechar=None):
    entry = MagicMock()
    entry.name = name
    entry.format = fmt
    entry.path = Path(path)
    entry.error_count = 0
    entry.delimiter = delimiter
    entry.quotechar = quotechar
    return entry


# ---------------------------------------------------------------------------
# _parse_load — flag parsing
# ---------------------------------------------------------------------------

def test_parse_load_no_flags(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    path_str, name, no_header, delimiter, quotechar = _parse_load(f":load {f}")
    assert no_header is False
    assert delimiter is None
    assert quotechar is None


def test_parse_load_delimiter_alias():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter semicolon")
    assert delimiter == ";"


def test_parse_load_delimiter_alias_tab():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter tab")
    assert delimiter == "\t"


def test_parse_load_delimiter_alias_pipe():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter pipe")
    assert delimiter == "|"


def test_parse_load_delimiter_alias_caret():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter caret")
    assert delimiter == "^"


def test_parse_load_delimiter_alias_comma():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter comma")
    assert delimiter == ","


def test_parse_load_delimiter_raw_char():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter |")
    assert delimiter == "|"


def test_parse_load_delimiter_multichar():
    _, _, _, delimiter, _ = _parse_load(":load data.csv --delimiter ||")
    assert delimiter == "||"


def test_parse_load_quotechar_single_quote():
    _, _, _, _, quotechar = _parse_load(":load data.csv --quotechar \"'\"")
    assert quotechar == "'"


def test_parse_load_quotechar_too_long_raises():
    with pytest.raises(ValueError, match="single character"):
        _parse_load(":load data.csv --quotechar ab")


def test_parse_load_delimiter_missing_value_raises():
    with pytest.raises(ValueError, match="requires a value"):
        _parse_load(":load data.csv --delimiter")


def test_parse_load_quotechar_missing_value_raises():
    with pytest.raises(ValueError, match="requires a value"):
        _parse_load(":load data.csv --quotechar")


def test_parse_load_unknown_flag_raises():
    with pytest.raises(ValueError, match="Unknown flag"):
        _parse_load(":load data.csv --foo")


def test_parse_load_all_flags_together(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a;b\n1;2\n")
    path_str, name, no_header, delimiter, quotechar = _parse_load(
        f":load {f} as mydata --no-header --delimiter semicolon --quotechar '"
    )
    assert no_header is True
    assert delimiter == ";"
    assert quotechar == "'"
    assert name == "mydata"


# ---------------------------------------------------------------------------
# handle_command :load — passes flags through to session.load
# ---------------------------------------------------------------------------

def test_load_delimiter_passed_to_session(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("a;b\n1;2\n")
    entry = _mock_entry(name="sales", fmt="csv", path=str(csv), delimiter=";")
    session = _make_session(load_return=entry)
    handle_command(f":load {csv} --delimiter semicolon", session)
    session.load.assert_called_once_with(
        "sales", str(csv).replace("\\", "/"),
        no_header=False, column_names=None,
        delimiter=";", quotechar=None,
    )


def test_load_quotechar_passed_to_session(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("a,b\n1,2\n")
    entry = _mock_entry(name="sales", fmt="csv", path=str(csv), quotechar="'")
    session = _make_session(load_return=entry)
    handle_command(f":load {csv} --quotechar \"'\"", session)
    session.load.assert_called_once_with(
        "sales", str(csv).replace("\\", "/"),
        no_header=False, column_names=None,
        delimiter=None, quotechar="'",
    )


def test_load_unknown_flag_returns_error(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("a,b\n1,2\n")
    session = _make_session()
    result = handle_command(f":load {csv} --bad-flag", session)
    assert "Unknown flag" in result


def test_load_quotechar_too_long_returns_error(tmp_path):
    csv = tmp_path / "sales.csv"
    csv.write_text("a,b\n1,2\n")
    session = _make_session()
    result = handle_command(f":load {csv} --quotechar ab", session)
    assert "single character" in result


# ---------------------------------------------------------------------------
# :schema — delimiter/quotechar display
# ---------------------------------------------------------------------------

def test_schema_shows_default_delimiter_for_csv():
    session = MagicMock()
    entry = _mock_entry(fmt="csv", delimiter=None, quotechar=None)
    session.catalog.get.return_value = entry
    session.schema.return_value = (
        ["column", "type", "nullable"],
        [("a", "VARCHAR", "True")],
    )
    session.get_warnings.return_value = []
    result = handle_command(":schema sample", session)
    assert "Delimiter" in result
    assert "(default)" in result


def test_schema_shows_custom_delimiter_for_csv():
    session = MagicMock()
    entry = _mock_entry(fmt="csv", delimiter=";", quotechar=None)
    session.catalog.get.return_value = entry
    session.schema.return_value = (
        ["column", "type", "nullable"],
        [("a", "VARCHAR", "True")],
    )
    session.get_warnings.return_value = []
    result = handle_command(":schema sample", session)
    assert "Delimiter" in result
    assert "';'" in result or ";" in result


def test_schema_no_delimiter_section_for_parquet():
    session = MagicMock()
    entry = _mock_entry(fmt="parquet", delimiter=None, quotechar=None)
    session.catalog.get.return_value = entry
    session.schema.return_value = (
        ["column", "type", "nullable"],
        [("a", "INT32", "True")],
    )
    session.get_warnings.return_value = []
    result = handle_command(":schema sample", session)
    assert "Delimiter" not in result