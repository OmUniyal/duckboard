from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from duckboard.repl import run_repl


def _make_session(cols=None, rows=None):
    session = MagicMock()
    session.fetch.return_value = (cols or ["col"], rows or [("val",)])
    return session


# ---------------------------------------------------------------------------
# 1. Valid SQL executes and prints box
# ---------------------------------------------------------------------------
def test_valid_sql_prints_table(capsys):
    session = _make_session(cols=["color"], rows=[("red",), ("blue",)])
    inputs = iter(["SELECT color FROM sample;", "quit"])
    with patch("duckboard.repl._read_input", side_effect=inputs):
        run_repl(session)
    out = capsys.readouterr().out
    assert "color" in out
    assert "red" in out


# ---------------------------------------------------------------------------
# 2. Bad SQL prints error and continues — next query still works
# ---------------------------------------------------------------------------
def test_bad_sql_prints_error_and_continues(capsys):
    session = MagicMock()
    session.fetch.side_effect = [Exception("syntax error"), (["id"], [(1,)])]
    inputs = iter(["BAD SQL;", "SELECT id FROM t;", "quit"])
    with patch("duckboard.repl._read_input", side_effect=inputs):
        run_repl(session)
    out = capsys.readouterr().out
    assert "Error: syntax error" in out
    assert "id" in out


# ---------------------------------------------------------------------------
# 3. :quit exits cleanly
# ---------------------------------------------------------------------------
def test_quit_command_exits(capsys):
    session = _make_session()
    inputs = iter([":quit"])
    with patch("duckboard.repl._read_input", side_effect=inputs):
        run_repl(session)
    out = capsys.readouterr().out
    assert "Bye." in out


# ---------------------------------------------------------------------------
# 4. Ctrl+D (EOFError) exits cleanly
# ---------------------------------------------------------------------------
def test_eof_exits_cleanly(capsys):
    session = _make_session()
    with patch("duckboard.repl._read_input", side_effect=EOFError):
        run_repl(session)
    out = capsys.readouterr().out
    assert "Bye." in out


# ---------------------------------------------------------------------------
# 5. Multi-line SQL accumulates until semicolon
# ---------------------------------------------------------------------------
def test_multiline_sql_executes_on_semicolon(capsys):
    session = _make_session(cols=["n"], rows=[(42,)])
    inputs = iter([
        "SELECT COUNT(*)",
        "FROM sample;",
        "quit",
    ])
    with patch("duckboard.repl._read_input", side_effect=inputs):
        run_repl(session)
    session.fetch.assert_called_once_with("SELECT COUNT(*) FROM sample")


# ---------------------------------------------------------------------------
# 6. Empty line resets buffer
# ---------------------------------------------------------------------------
def test_empty_line_resets_buffer(capsys):
    session = _make_session(cols=["n"], rows=[(1,)])
    inputs = iter([
        "SELECT *",   # start accumulating
        "",           # empty — resets buffer
        "SELECT n FROM t;",  # fresh statement
        "quit",
    ])
    with patch("duckboard.repl._read_input", side_effect=inputs):
        run_repl(session)
    # fetch should be called once with only the second statement
    session.fetch.assert_called_once_with("SELECT n FROM t")


# ---------------------------------------------------------------------------
# 7. :command dispatches to handle_command
# ---------------------------------------------------------------------------
def test_command_dispatches_to_handle_command(capsys):
    session = _make_session()
    with (
        patch("duckboard.repl._read_input", side_effect=iter([":tables", "quit"])),
        patch("duckboard.commands.handle_command", return_value="(no tables loaded)") as mock_cmd,
    ):
        run_repl(session)
    mock_cmd.assert_called_once_with(":tables", session, None)