from __future__ import annotations
import pytest
from duckboard.formatter import format_table


# ── Truncation ────────────────────────────────────────────────────────────────

def test_no_truncation_when_fits():
    cols = ["a", "b"]
    rows = [("hi", "there")]
    out = format_table(cols, rows, terminal_width=80)
    assert "hi" in out
    assert "there" in out
    # no ellipsis injected
    assert "…" not in out


def test_truncation_adds_ellipsis():
    # 3 columns each naturally 20 chars wide, terminal too narrow to fit all
    cols = ["col_a", "col_b", "col_c"]
    long_val = "x" * 20
    rows = [(long_val, long_val, long_val)]
    out = format_table(cols, rows, terminal_width=40)
    assert "…" in out


def test_truncation_all_lines_same_width():
    cols = ["name", "value", "extra"]
    rows = [
        ("alice", "something long here", "abc"),
        ("bob",   "short",               "defgh"),
    ]
    out = format_table(cols, rows, terminal_width=40)
    lines = [l for l in out.splitlines() if l.startswith("│")]
    assert len(set(len(l) for l in lines)) == 1


def test_header_truncated_when_over_budget():
    # column name longer than its budget gets truncated too
    cols = ["a_very_long_column_name", "b"]
    rows = [("x", "y")]
    out = format_table(cols, rows, terminal_width=20)
    # header is present but truncated
    assert "a_very_lon" not in out.splitlines()[1] or "…" in out


def test_minimum_column_width_is_four():
    # absurdly narrow but still above the vertical fallback threshold
    # 2 cols: budget must give each at least 4
    cols = ["a", "b"]
    rows = [("1", "2")]
    # 2 cols: total_needed = 2 + 3*2+1 = 9; terminal=15 → budget=8 → 4 each
    out = format_table(cols, rows, terminal_width=15)
    assert "…" not in out  # values fit in 4 chars, no truncation needed


def test_narrow_terminal_falls_back_to_vertical():
    cols = ["col1", "col2", "col3"]
    rows = [("a", "b", "c")]
    # budget < 4*3=12 → fallback
    out = format_table(cols, rows, terminal_width=10)
    assert "terminal too narrow" in out
    assert "1. row" in out


# ── Vertical mode ─────────────────────────────────────────────────────────────

def test_vertical_basic_structure():
    cols = ["id", "name"]
    rows = [(1, "alice"), (2, "bob")]
    out = format_table(cols, rows, vertical=True)
    assert "1. row" in out
    assert "2. row" in out
    assert "  id: 1" in out
    assert "name: alice" in out


def test_vertical_label_right_aligned():
    cols = ["x", "longer_name"]
    rows = [(1, "a")]
    out = format_table(cols, rows, vertical=True)
    lines = out.splitlines()
    value_lines = [l for l in lines if ": " in l and "row" not in l]
    # all value lines should start at the same column position
    colon_positions = [l.index(":") for l in value_lines]
    assert len(set(colon_positions)) == 1


def test_vertical_zero_rows():
    cols = ["a", "b"]
    rows = []
    out = format_table(cols, rows, vertical=True)
    assert out == "(0 rows)"
    assert "row" in out
    assert "***" not in out


def test_vertical_max_rows_cap():
    cols = ["n"]
    rows = [(i,) for i in range(60)]
    out = format_table(cols, rows, max_rows=50, vertical=True)
    assert "(showing 50 of 60 rows)" in out
    assert "51. row" not in out


def test_vertical_hint_max_rows():
    # max_rows=5 passed in (simulating /*+ vertical_result(5) */ parsed by repl)
    cols = ["n"]
    rows = [(i,) for i in range(20)]
    out = format_table(cols, rows, max_rows=5, vertical=True)
    assert "(showing 5 of 20 rows)" in out
    assert "6. row" not in out


def test_vertical_no_truncation():
    # vertical mode should never truncate cell values
    cols = ["description"]
    long_val = "x" * 200
    rows = [(long_val,)]
    out = format_table(cols, rows, vertical=True, terminal_width=40)
    assert long_val in out
    assert "…" not in out


def test_vertical_single_row_footer():
    cols = ["a"]
    rows = [("only",)]
    out = format_table(cols, rows, vertical=True)
    assert "(1 row)" in out