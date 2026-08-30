"""Tests for the interactive REPL loop."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from duckboard.repl import run_repl
from duckboard.session import DuckboardSession


def _make_session(cols=None, rows=None):
    session = MagicMock()
    if cols is not None:
        session.fetch.return_value = (cols, rows or [])
    return session


def _mock_input(*lines: str):
    """Return a callable that serves lines in order, then raises EOFError."""
    it = iter(lines)
    def _fn(prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    return _fn


def test_valid_sql_prints_table(capsys):
    session = _make_session(cols=["color"], rows=[("red",), ("blue",)])
    run_repl(session, _input_fn=_mock_input("SELECT color FROM sample;", "quit"))
    out = capsys.readouterr().out
    assert "red" in out
    assert "blue" in out


def test_bad_sql_prints_error_and_continues(capsys):
    session = MagicMock()
    session.fetch.side_effect = [Exception("syntax error"), (["id"], [(1,)])]
    run_repl(session, _input_fn=_mock_input("BAD SQL;", "SELECT id FROM t;", "quit"))
    out = capsys.readouterr().out
    assert "syntax error" in out


def test_quit_command_exits(capsys):
    session = _make_session()
    run_repl(session, _input_fn=_mock_input(":quit"))
    out = capsys.readouterr().out
    assert "Bye" in out


def test_eof_exits_cleanly(capsys):
    session = _make_session()
    def _eof(prompt: str = "") -> str:
        raise EOFError
    run_repl(session, _input_fn=_eof)
    out = capsys.readouterr().out
    assert "Bye" in out


def test_multiline_sql_executes_on_semicolon(capsys):
    session = _make_session(cols=["n"], rows=[(42,)])
    run_repl(session, _input_fn=_mock_input(
        "SELECT COUNT(*)",
        "FROM sample;",
        "quit",
    ))
    out = capsys.readouterr().out
    assert "42" in out


def test_empty_line_resets_buffer(capsys):
    session = _make_session(cols=["n"], rows=[(1,)])
    run_repl(session, _input_fn=_mock_input(
        "SELECT *",   # start accumulating
        "",           # empty — resets buffer
        "SELECT n FROM t;",
        "quit",
    ))
    # only one fetch call — the abandoned SELECT * was discarded
    assert session.fetch.call_count == 1


def test_command_dispatches_to_handle_command(capsys):
    session = _make_session()
    with patch("duckboard.commands.handle_command", return_value="(no tables loaded)") as mock_cmd:
        run_repl(session, _input_fn=_mock_input(":tables", "quit"))
    out = capsys.readouterr().out
    assert "(no tables loaded)" in out
    mock_cmd.assert_called_once()