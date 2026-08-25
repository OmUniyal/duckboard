# Changelog

All notable changes to duckboard are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.1] — 2026-08-25

### Fixed
- `:save` export rewritten to use Python `csv.writer` for CSV and `json` module
  for JSON — eliminates row-by-row DuckDB insertion that caused exports to hang
  on large files (19K rows now exports instantly)
- Parquet export wrapped in explicit transaction to reduce overhead
- `Ctrl+C` now interrupts stuck commands and long-running queries gracefully
  instead of crashing the REPL

### Added
- `src/duckboard/__main__.py` — enables `python -m duckboard` as an alternative
  launch method for environments where the script entry point is blocked

## [0.2.0] — 2026-08-23

### Added
- Structural validation on `:load` for CSV/PSV/TSV files — scans first 1,000 rows,
  flags column count mismatches into `_errors_{name}` table
- Type anomaly detection — flags rows where a minority of values in a VARCHAR column
  are numeric (e.g. a number in a gender column)
- `_errors_{name}` DuckDB table with columns: `row_number`, `raw_line`,
  `error_type`, `column_name`, `reason`
- `:load` now shows validation error count and heuristic warnings after load
- `:tables` shows `[!N]` error indicator for tables with validation errors
- No-header heuristic — warns if first row of a CSV looks like data, not labels
- `--no-header` flag on `:load` — prompts for column names or auto-generates col1,
  col2, col3, …
- `:rename_column table old_name new_name` — rename a column in a loaded table
- `:export_errors table "path"` — export malformed rows to CSV/Parquet/JSON
- `:export_clean table "path"` — export only validated rows to CSV/Parquet/JSON
- `:clear` / `:cls` — clear the terminal
- 22 new tests (test_validation.py, test_commands_v2.py); total: 67 passing

## [0.1.0] — 2026-08-20

### Added
- `DuckboardSession` core engine with DuckDB connection management
- `FileCatalog` — register files as queryable DuckDB views
- Supported formats: CSV, TSV, PSV (pipe-separated), Parquet, JSON, JSONL, NDJSON
- `formatter.py` — box-drawing terminal output with numeric right-alignment,
  NULL rendering, 50-row display cap, and row count footer
- Interactive REPL (`repl.py`) with:
  - Semicolon-terminated multiline SQL
  - `:command` dispatch
  - readline history via `pyreadline3` (optional dep, Windows)
  - Clean exit on `:quit`, `:q`, `exit`, `quit`, Ctrl+D
- REPL commands: `:load`, `:tables`, `:schema`, `:save`, `:unload`, `:pwd`
- `:load` — quoted path support, optional `as name` (defaults to filename stem)
- `:save` — auto-detect format from extension, explicit `--csv/--parquet/--json` override
- Large export warning prompt (2,000+ rows)
- Windows path normalization throughout (backslash → forward slash)
- `cli.py` entrypoint with `--version` and `--help`
- 45 tests passing across catalog, session, formatter, REPL, commands, CLI, and smoke test