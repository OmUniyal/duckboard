# duckboard

File-first local SQL workspace for CSV, Parquet, PSV, and JSON — powered by [DuckDB](https://duckdb.org/).

Load files once, query by name with plain SQL, export results. Terminal-native alternative to spinning up a notebook for quick file questions.

> **Status:** v0.3.0 — available on [PyPI](https://pypi.org/project/duckboard/).

## Install

```powershell
pip install duckboard
```

**Development install:**

```powershell
git clone https://github.com/OmUniyal/duckboard
cd duckboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Quickstart

```powershell
duckboard
```

```
duckboard> :load examples/sample.csv as sample
duckboard> SELECT color, COUNT(*) AS n FROM sample GROUP BY 1;
┌────────┬───┐
│ color  │ n │
├────────┼───┤
│ blue   │ 1 │
│ green  │ 1 │
│ red    │ 2 │
└────────┴───┘
(3 rows)
duckboard> :save results.csv
Saved 3 rows to results.csv
duckboard> :quit
Bye.
```

## Supported file formats

| Extension                    | Format               |
|------------------------------|----------------------|
| `.csv`, `.tsv`               | CSV                  |
| `.psv`                       | PSV (pipe-separated) |
| `.parquet`                   | Parquet              |
| `.json`, `.jsonl`, `.ndjson` | JSON                 |

## REPL commands

| Command | Description |
|---------|-------------|
| `:load "path" [as name] [--no-header]` | Load a file as a queryable table. Name defaults to filename stem. Use `--no-header` if the file has no header row — duckboard will prompt for column names or auto-generate them. |
| `:tables` | List all loaded tables with format, path, and validation status. |
| `:schema <table>` | Show column names, types, and nullability. Includes load warnings when present. |
| `:save "path" [--csv\|--parquet\|--json]` | Save last query result to a file. Format auto-detected from extension; use flag to override. |
| `:unload <table>` | Remove a loaded table from the session. |
| `:unload all` | Remove every loaded table in one shot. |
| `:rename_column table old_name new_name` | Rename a column in a loaded table. |
| `:export_errors table "path" [--csv\|--parquet\|--json]` | Export rows that failed validation to a file. |
| `:export_clean table "path" [--csv\|--parquet\|--json]` | Export only validated rows to a file. |
| `:pwd` | Show current working directory. |
| `:clear` / `:cls` | Clear the terminal. |
| `:quit` / `:q` / `exit` / `quit` / `Ctrl+D` | Exit duckboard. |

## Vertical output

Wide results can be viewed one row at a time using vertical mode. Two ways to trigger it:

**`\G` suffix** — append immediately before the semicolon:
```
duckboard> SELECT * FROM orders WHERE id = 1\G;
*************************** 1. row ***************************
        id: 1
  customer: Alice
   revenue: 12345.67

(1 row)
```

**Oracle-style hint** — inline, with a custom display row cap:
```sql
SELECT /*+ vertical_result(5) */ * FROM orders;
```
This shows up to 5 rows vertically. The full result set is still held in memory for `:save`.

## Tab autocomplete

duckboard supports tab completion (requires `pyreadline3` on Windows, built-in `readline` on Linux/macOS):

- **Command names** — type `:s` and press Tab to expand to `:schema`, `:save`, etc.
- **Table names** — after `:schema`, `:unload`, `:export_errors`, and similar commands
- **File paths** — after `:load`
- **SQL keywords** — `SEL` → `SELECT`, `FR` → `FROM`, etc.

Install the readline extra on Windows:
```powershell
pip install duckboard[readline]
```

## Data quality

When a file is loaded, duckboard validates it and reports issues automatically.

**Full-file structural validation** (CSV/PSV/TSV): scans every row, flags column count mismatches into `_errors_{name}`. No row limit — a bad row at position 15,000 is caught just like one at position 5.

**Type anomaly detection**: flags rows where a numeric value appears in a predominantly string column (e.g. a number in a `gender` column).

**Residual row-count cross-check**: after loading, duckboard compares the raw line count against what DuckDB actually loaded. Any shortfall beyond known errors is surfaced as a warning with exact counts so the root cause can be tracked down.

`:load` output reflects what was found:

```
# Clean
Loaded 'orders' from orders.csv  (csv)

# Known validation errors
Loaded 'orders' from orders.csv  (csv)
  2 validation error(s) found.
  → :export_errors orders  to inspect  |  :export_clean orders  for clean rows

# DuckDB dropped rows silently (cause unknown)
Loaded 'orders' from orders.csv  (csv)
  2 row(s) were dropped by DuckDB but not captured in the error table
  (cause unknown — may be encoding, embedded nulls, or a DuckDB type coercion issue).
  Raw line count: 20000, loaded: 19998, known errors: 0.
```

All known errors are stored in `_errors_{name}` for the duration of the session:
```sql
SELECT * FROM _errors_orders;
```

The `:tables` command shows status for every loaded table:

```
┌────────┬────────┬────────────┬────────────┐
│ name   │ format │ path       │ errors     │
├────────┼────────┼────────────┼────────────┤
│ orders │ csv    │ orders.csv │ [!2]       │
│ events │ parquet│ events.prq │ [!?]       │
│ mixed  │ csv    │ mixed.csv  │ [!2 +?]    │
│ sample │ csv    │ sample.csv │ ok         │
└────────┴────────┴────────────┴────────────┘
```

`[!N]` — N known errors in the error table, exportable via `:export_errors`.
`[!?]` — rows dropped by DuckDB, not in error table, cause TBD.
`[!N +?]` — both.

## Notes

- Queries display a maximum of 50 rows in the terminal. Full results are always exported via `:save`.
- Large exports (2,000+ rows) prompt for confirmation before writing.
- On Windows, use forward slashes in paths: `:load data/sales.csv` not `:load data\sales.csv`.
- Multi-line SQL is supported — statements execute on semicolon.
- Validation runs on CSV and PSV files only. Parquet and JSON validation is planned for v0.4.0.
- `python -m duckboard` works as an alternative launch method if the script entry point is unavailable.

## Read more

[I built a terminal SQL workspace for CSV files — and made it catch bad data automatically](https://dev.to/omuniyal/i-built-a-terminal-sql-workspace-for-csv-files-and-made-it-catch-bad-data-automatically-mpl) — dev.to

## Project layout

```
src/duckboard/
├── __main__.py     # Enables python -m duckboard
├── session.py      # DuckboardSession — owns DuckDB connection + state
├── catalog.py      # Registered file → view mappings, validation, cross-check
├── repl.py         # Interactive REPL loop with \G and hint intercept
├── commands.py     # All REPL commands
├── formatter.py    # Box-drawing output, truncation, and vertical mode
├── completer.py    # Tab autocomplete for commands, tables, paths, SQL keywords
├── cli.py          # CLI entry point
└── exceptions.py   # DuckboardError hierarchy
```

## License

MIT