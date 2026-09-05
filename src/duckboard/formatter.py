"""Format query results for terminal display."""

from __future__ import annotations

import shutil


def format_table(
    columns: list[str],
    rows: list[tuple],
    max_rows: int = 50,
    vertical: bool = False,
    terminal_width: int | None = None,
) -> str:
    def _cell(val: object) -> str:
        if val is None:
            return "NULL"
        if isinstance(val, float) and val.is_integer():
            return f"{val:.0f}"
        return str(val)

    def _is_numeric_col(col_idx: int) -> bool:
        for row in rows:
            val = row[col_idx]
            if val is not None:
                return isinstance(val, (int, float))
        return False

    rendered: list[list[str]] = [[_cell(v) for v in row] for row in rows]
    total = len(rows)
    display_rows = rendered[:max_rows]
    n_cols = len(columns)

    def _footer() -> str:
        if total == 0:
            return "(0 rows)"
        if total > max_rows:
            return f"(showing {max_rows} of {total} rows)"
        return f"({total} {'row' if total == 1 else 'rows'})"

    # ── Vertical mode ─────────────────────────────────────────────────────────
    if vertical:
        if total == 0:
            return "(0 rows)"
        label_w = max(len(c) for c in columns)
        stars = "*" * 27
        parts: list[str] = []
        for i, row in enumerate(display_rows, 1):
            parts.append(f"{stars} {i}. row {stars}")
            for col, cell in zip(columns, row):
                parts.append(f"{col.rjust(label_w)}: {cell}")
            parts.append("")  # blank line between rows
        if parts and parts[-1] == "":
            parts.pop()
        parts.append("")
        parts.append(_footer())
        return "\n".join(parts)

    # ── Horizontal mode ───────────────────────────────────────────────────────
    numeric = [_is_numeric_col(i) for i in range(n_cols)]

    natural_widths = [
        max(len(col), *(len(r[i]) for r in rendered) if rendered else (len(col),))
        for i, col in enumerate(columns)
    ]

    tw = (
        terminal_width
        if terminal_width is not None
        else shutil.get_terminal_size(fallback=(80, 24)).columns
    )
    total_needed = sum(natural_widths) + 3 * n_cols + 1
    col_widths = natural_widths[:]

    if total_needed > tw:
        budget = tw - (3 * n_cols + 1)
        if budget < 4 * n_cols:
            from duckboard.exceptions import TerminalTooNarrowError
            raise TerminalTooNarrowError(
                "terminal too narrow to display table horizontally"
            )
        # Greedy proportional assignment, floor 4 per column
        order = sorted(range(n_cols), key=lambda i: natural_widths[i], reverse=True)
        remaining = budget
        for rank, idx in enumerate(order):
            remaining_count = n_cols - rank
            w = max(4, min(natural_widths[idx], remaining // remaining_count))
            col_widths[idx] = w
            remaining -= w

    def _truncate(text: str, width: int) -> str:
        return text if len(text) <= width else text[: width - 1] + "…"

    def _pad(text: str, width: int, right_align: bool) -> str:
        return text.rjust(width) if right_align else text.ljust(width)

    top    = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
    sep    = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
    bottom = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"

    header = "│" + "│".join(
        f" {_pad(_truncate(col, col_widths[i]), col_widths[i], numeric[i])} "
        for i, col in enumerate(columns)
    ) + "│"

    data_lines = [
        "│" + "│".join(
            f" {_pad(_truncate(row[i], col_widths[i]), col_widths[i], numeric[i])} "
            for i in range(n_cols)
        ) + "│"
        for row in display_rows
    ]

    lines = [top, header, sep, *data_lines, bottom, _footer()]
    return "\n".join(lines)