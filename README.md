# duckboard

File-first local SQL workspace for CSV, Parquet, and JSON — powered by [DuckDB](https://duckdb.org/).

Load files once, query by name, export full results. Terminal-native alternative to spinning up a notebook for quick file questions.

> **Status:** Pre-alpha — building toward basic file querying before any PyPI release.

## Install (development)

```powershell
cd C:\Users\omuni\Projects\duckboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Quickstart (planned)

```powershell
duckboard
```

```
duckboard> :load examples/sample.csv as sample
duckboard> SELECT color, COUNT(*) AS n FROM sample GROUP BY 1;
```

## Project layout

```
src/duckboard/
├── session.py      # DuckboardSession — owns DuckDB connection + state
├── catalog.py      # Registered file → view mappings
├── repl.py         # Interactive REPL loop
├── commands.py     # :load, :tables, :schema, :save, etc.
├── formatter.py    # Pretty table output for query results
├── cli.py          # CLI entry point
└── exceptions.py   # DuckboardError hierarchy
```

## License

MIT
