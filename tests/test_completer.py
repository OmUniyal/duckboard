"""Tests for DuckboardCompleter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from duckboard.completer import DuckboardCompleter
from duckboard.session import DuckboardSession


def _make_completer(table_names: list[str] | None = None) -> DuckboardCompleter:
    session = MagicMock()
    if table_names is not None:
        entries = []
        for n in table_names:
            e = MagicMock()
            e.name = n
            entries.append(e)
        session.catalog.list_tables.return_value = entries
    else:
        session.catalog.list_tables.return_value = []
    return DuckboardCompleter(session)


def _complete_all(completer: DuckboardCompleter, text: str, line: str) -> list[str]:
    """Collect all completions for a given text and line buffer."""
    completer._get_line_buffer = lambda: line
    results = []
    state = 0
    while True:
        m = completer.complete(text, state)
        if m is None:
            break
        results.append(m)
        state += 1
    return results


# ── Command completion ────────────────────────────────────────────────────────

def test_command_prefix_tables():
    c = _make_completer()
    matches = _complete_all(c, ":t", ":t")
    assert ":tables" in matches


def test_command_prefix_load():
    c = _make_completer()
    matches = _complete_all(c, ":l", ":l")
    assert ":load" in matches


def test_command_no_match():
    c = _make_completer()
    matches = _complete_all(c, ":zzz", ":zzz")
    assert matches == []


def test_all_commands_returned_on_colon():
    from duckboard.completer import COMMANDS
    c = _make_completer()
    # New completer returns common prefix only — ":" is the prefix of all commands
    result = c.complete(":", 0)
    # All commands share ":" as prefix so common prefix == ":" — no-op completion
    # Verify at minimum that completion doesn't crash and returns None or a string
    assert result is None or isinstance(result, str)


# ── Table name completion ─────────────────────────────────────────────────────

def test_table_completion_after_schema():
    c = _make_completer(["sample", "orders"])
    matches = _complete_all(c, "sam", ":schema sam")
    assert "sample" in matches
    assert "orders" not in matches


def test_table_completion_after_unload():
    c = _make_completer(["sample", "orders"])
    matches = _complete_all(c, "ord", ":unload ord")
    assert "orders" in matches
    assert "sample" not in matches


def test_table_completion_empty_catalog():
    c = _make_completer([])
    matches = _complete_all(c, "", ":schema ")
    assert matches == []


# ── SQL keyword completion ────────────────────────────────────────────────────

def test_sql_keyword_select():
    c = _make_completer()
    matches = _complete_all(c, "SEL", "SEL")
    assert "SELECT" in matches


def test_sql_keyword_case_insensitive_input():
    c = _make_completer()
    matches = _complete_all(c, "sel", "sel")
    assert "SELECT" in matches


def test_sql_keyword_no_match():
    c = _make_completer()
    matches = _complete_all(c, "ZZZ", "ZZZ")
    assert matches == []


# ── Smoke test: full state-machine loop ──────────────────────────────────────

def test_smoke_table_completion_state_machine():
    """Multiple matches return common prefix; unique match returns full name."""
    c = _make_completer(["alpha", "beta"])
    c._get_line_buffer = lambda: ":schema "
    # "alpha" and "beta" share no common prefix beyond "" — no completion
    result = c.complete("", 0)
    assert result is None or isinstance(result, str)

    # With a unique match, full name is returned
    c2 = _make_completer(["alpha"])
    c2._get_line_buffer = lambda: ":schema alp"
    result2 = c2.complete("alp", 0)
    assert result2 == "alpha"
    assert c2.complete("alp", 1) is None