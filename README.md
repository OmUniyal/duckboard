# duckboard

File-first local SQL workspace for CSV, Parquet, PSV, and JSON — powered by [DuckDB](https://duckdb.org/).

Load files once, query by name with plain SQL, export results. Terminal-native alternative to spinning up a notebook for quick file questions.

> **Status:** Alpha — core functionality complete, PyPI release coming soon.

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

| Extension              | Format  |
|------------------------|---------|
| `.csv`, `.tsv`         | CSV     |
| `.psv`                 | PSV (pipe-separated) |
| `.parquet`             | Parquet |
| `.json`, `.jsonl`, `.ndjson` | JSON |

## REPL commands

| Command | Description |
|---------|-------------|
| `:load "path/to/file.ext" [as name]` | Load a file as a queryable table. Name defaults to filename stem. |
| `:tables` | List all loaded tables with format and path. |
| `:schema <table>` | Show column names, types, and nullability for a table. |
| `:save "path/to/output.ext" [--csv\|--parquet\|--json]` | Save last query result to a file. Format auto-detected from extension; use flag to override. |
| `:unload <table>` | Remove a loaded table from the session. |
| `:pwd` | Show current working directory. |
| `:quit` / `:q` / `exit` / `quit` / `Ctrl+D` | Exit duckboard. |

## Notes

- Queries display a maximum of 50 rows in the terminal. Full results are always exported via `:save`.
- Large exports (2,000+ rows) prompt for confirmation before writing.
- On Windows, use forward slashes in paths: `:load data/sales.csv` not `:load data\sales.csv`.
- Multi-line SQL is supported — statements execute on semicolon.

## Project layout

```
src/duckboard/
├── session.py      # DuckboardSession — owns DuckDB connection + state
├── catalog.py      # Registered file → view mappings
├── repl.py         # Interactive REPL loop
├── commands.py     # :load, :tables, :schema, :save, :unload, :pwd
├── formatter.py    # Box-drawing table output for query results
├── cli.py          # CLI entry point
└── exceptions.py   # DuckboardError hierarchy
```

## License

MIT