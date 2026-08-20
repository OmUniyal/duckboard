# Changelog

All notable changes to duckboard are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-08-20

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

## [Unreleased] - v0.2.0

### Planned
- CSV/PSV/TSV validation on `:load` (column count mismatch detection)
- No-header detection with `--no-header` flag and column name prompt
- Malformed row storage in `_errors_{name}` session table
- `:export_errors <table>` and `:export_clean <table>` commands
- `:tables` warning indicator for tables with errors