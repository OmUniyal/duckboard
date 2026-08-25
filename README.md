# duckboard

File-first local SQL workspace for CSV, Parquet, PSV, and JSON — powered by [DuckDB](https://duckdb.org/).

Load files once, query by name with plain SQL, export results. Terminal-native alternative to spinning up a notebook for quick file questions.

> **Status:** v0.2.1 — available on [PyPI](https://pypi.org/project/duckboard/).

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
| `:schema <table>` | Show column names, types, and nullability for a table. |
| `:save "path" [--csv\|--parquet\|--json]` | Save last query result to a file. Format auto-detected from extension; use flag to override. |
| `:unload <table>` | Remove a loaded table from the session. |
| `:rename_column table old_name new_name` | Rename a column in a loaded table. |
| `:export_errors table "path" [--csv\|--parquet\|--json]` | Export rows that failed validation to a file. |
| `:export_clean table "path" [--csv\|--parquet\|--json]` | Export only validated rows to a file. |
| `:pwd` | Show current working directory. |
| `:clear` / `:cls` | Clear the terminal. |
| `:quit` / `:q` / `exit` / `quit` / `Ctrl+D` | Exit duckboard. |

## Data quality

When a CSV or PSV file is loaded, duckboard automatically validates the first 1,000 rows and reports two types of issues:

**Structural errors** — rows whose field count doesn't match the header:
```
duckboard> :load "sales.csv" as sales
Loaded 'sales' from sales.csv  (csv)
  1 validation error(s) found. Run 'SELECT * FROM _errors_sales' to inspect.
```

**Type anomalies** — rows where a numeric value appears in a predominantly string column (e.g. a number in a `gender` column).

All errors are stored in `_errors_{name}` for the duration of the session:
```sql
SELECT * FROM _errors_sales;
```

The `:tables` command shows an error indicator for affected tables:
```
┌────────┬────────┬───────────┬────────┐
│ name   │ format │ path      │ errors │
├────────┼────────┼───────────┼────────┤
│ sales  │ csv    │ sales.csv │ [!1]   │
│ orders │ csv    │ orders.csv│ ok     │
└────────┴────────┴───────────┴────────┘
```

## Notes

- Queries display a maximum of 50 rows in the terminal. Full results are always exported via `:save`.
- Large exports (2,000+ rows) prompt for confirmation before writing.
- On Windows, use forward slashes in paths: `:load data/sales.csv` not `:load data\sales.csv`.
- Multi-line SQL is supported — statements execute on semicolon.
- Validation runs on CSV and PSV files only. Parquet and JSON validation is planned for v0.3.0.
- `python -m duckboard` works as an alternative launch method if the script entry point is unavailable.

## Read more

[I built a terminal SQL workspace for CSV files — and made it catch bad data automatically](https://dev.to/omuniyal/i-built-a-terminal-sql-workspace-for-csv-files-and-made-it-catch-bad-data-automatically-mpl) — dev.to

## Project layout

```
src/duckboard/
├── __main__.py     # Enables python -m duckboard
├── session.py      # DuckboardSession — owns DuckDB connection + state
├── catalog.py      # Registered file → view mappings + validation
├── repl.py         # Interactive REPL loop
├── commands.py     # All REPL commands
├── formatter.py    # Box-drawing table output for query results
├── cli.py          # CLI entry point
└── exceptions.py   # DuckboardError hierarchy
```

## License

MIT