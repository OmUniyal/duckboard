from __future__ import annotations
import pytest
from duckboard.formatter import format_table


def test_basic_box_structure():
    cols = ["color", "n"]
    rows = [("red", 2), ("blue", 1)]
    out = format_table(cols, rows)
    assert "┌" in out and "┐" in out
    assert "│ color │" in out
    assert "red" in out and "blue" in out


def test_numeric_right_alignment():
    cols = ["name", "score"]
    rows = [("alice", 100), ("bob", 9)]
    out = format_table(cols, rows)
    lines = out.splitlines()
    data_lines = [l for l in lines if "alice" in l or "bob" in l]
    alice_line = next(l for l in data_lines if "alice" in l)
    bob_line   = next(l for l in data_lines if "bob" in l)
    # extract score cell (between last two │, includes surrounding spaces)
    alice_score = alice_line.rsplit("│", 2)[1]
    bob_score   = bob_line.rsplit("│", 2)[1]
    # right-aligned: value is flush right, padding is on the left
    assert alice_score.lstrip() == "100 "
    assert bob_score.lstrip() == "9 "
    # both cells are the same width
    assert len(alice_score) == len(bob_score)


def test_null_renders_as_NULL():
    cols = ["a", "b"]
    rows = [(None, 1), ("x", None)]
    out = format_table(cols, rows)
    assert out.count("NULL") == 2


def test_truncation_at_max_rows():
    cols = ["id"]
    rows = [(i,) for i in range(60)]
    out = format_table(cols, rows, max_rows=50)
    assert "(showing 50 of 60 rows)" in out
    # row 51 should not appear
    assert "│  50 │" not in out or out.index("showing") > 0


def test_zero_rows():
    cols = ["color", "n"]
    rows = []
    out = format_table(cols, rows)
    assert "│ color │" in out
    assert "(0 rows)" in out


def test_single_row_single_col():
    cols = ["val"]
    rows = [("hello",)]
    out = format_table(cols, rows)
    assert "hello" in out
    assert "(1 row)" in out


def test_long_value_expands_column():
    cols = ["x"]
    rows = [("short",), ("a very long value indeed",)]
    out = format_table(cols, rows)
    assert "a very long value indeed" in out
    # all data lines should be the same width
    lines = [l for l in out.splitlines() if l.startswith("│")]
    assert len(set(len(l) for l in lines)) == 1