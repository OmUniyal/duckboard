"""Format query results for terminal display."""

from __future__ import annotations


def format_table(
    columns: list[str],
    rows: list[tuple],
    max_rows: int = 50,
) -> str:
    def _cell(val: object) -> str:
        return "NULL" if val is None else str(val)

    def _is_numeric_col(col_idx: int) -> bool:
        for row in rows:
            val = row[col_idx]
            if val is not None:
                return isinstance(val, (int, float))
        return False

    rendered: list[list[str]] = [[_cell(v) for v in row] for row in rows]
    total = len(rows)
    display_rows = rendered[:max_rows]

    col_widths = [
        max(len(col), *(len(r[i]) for r in rendered) if rendered else (len(col),))
        for i, col in enumerate(columns)
    ]
    numeric = [_is_numeric_col(i) for i in range(len(columns))]

    def _pad(text: str, width: int, right_align: bool) -> str:
        return text.rjust(width) if right_align else text.ljust(width)

    top    = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
    sep    = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
    bottom = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"

    header = "│" + "│".join(
        f" {_pad(col, col_widths[i], numeric[i])} "
        for i, col in enumerate(columns)
    ) + "│"

    data_lines = [
        "│" + "│".join(
            f" {_pad(row[i], col_widths[i], numeric[i])} "
            for i in range(len(columns))
        ) + "│"
        for row in display_rows
    ]

    lines = [top, header, sep, *data_lines, bottom]

    if total == 0:
        lines.append("(0 rows)")
    elif total > max_rows:
        lines.append(f"(showing {max_rows} of {total} rows)")
    else:
        lines.append(f"({total} {'row' if total == 1 else 'rows'})")

    return "\n".join(lines)
