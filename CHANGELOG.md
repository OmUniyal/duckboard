# Changelog

All notable changes to duckboard are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.4.0] — 2026-09-05

### Added
- `--delimiter <value>` flag on `:load` — accepts named aliases (`tab`, `pipe`,
  `semicolon`, `caret`, `comma`), any single character, or multi-char strings;
  `.tsv` files automatically default to tab delimiter without requiring the flag
- `--quotechar <char>` flag on `:load` — override the default `"` quote character;
  single character only
- `:schema` now shows delimiter and quote char for CSV/PSV tables — `(default)`
  when unset, explicit value when overridden
- All-null column check on every load (CSV, PSV, Parquet, JSON) — warns when a
  column has no non-null values; surfaced in `:schema` Warnings section
- JSONL/NDJSON line-level validation — full-file scan with `json.loads()`, no row
  cap; malformed lines captured in `_errors_{name}` with `error_type = json_parse`;
  progress indicator printed for files larger than 50 MB
- JSON schema consistency warning — when DuckDB infers a column as `JSON` type
  (mixed structure across records), a warning is added to `:schema`
- Non-tabular JSON guard for `.json` files — scalars and arrays of scalars raise
  `CatalogError` with a clear message instead of loading as a single-column table

### Fixed
- Vertical output no longer triggered automatically for wide tables — the terminal-
  too-narrow fallback previously switched silently to vertical mode and buried a
  warning under 50 rows of output; now raises `TerminalTooNarrowError` and prompts
  the user interactively (confirm vertical mode + choose row count)
- Large integer/float columns no longer displayed in scientific notation — whole-
  number floats (e.g. ID-style columns typed as `DOUBLE` by DuckDB) now render
  as integers (`412345678` instead of `4.12e+08`)

### Changed
- `--delimiter` and `--quotechar` are forwarded to both DuckDB `read_csv_auto`
  and the Python `csv` module structural scanner, ensuring consistent validation
  and query behaviour for non-default delimiters
- Multi-char delimiters bypass the Python structural scan (Python `csv.reader`
  does not support them) and rely on DuckDB + residual row-count cross-check only
- `CatalogEntry` now stores `delimiter` and `quotechar` fields; `rename_column`
  preserves them when reconstructing the view

### Tests
- 151 passing (up from 105 in v0.3.1)
- New: `test_catalog_v4.py` (12), `test_commands_v3.py` (21),
  `test_json_validation.py` (13), `test_formatter_v3.py` updated (1 change)

## [0.3.1] — 2026-08-30

### Fixed
- Tab autocomplete now works on Windows via `pyreadline3` — previous release
  silently fell back to no-op due to `pyreadline3` not exposing `set_completer`
  at module level; fix instantiates `Readline()` directly and wires it into
  the REPL input loop without mutating `builtins.input` globally
- Path completions filtered to supported file extensions only (`.csv`, `.tsv`,
  `.psv`, `.parquet`, `.json`, `.jsonl`, `.ndjson`) — previously all files in
  a directory were listed, flooding the console
- Common-prefix completion prevents console flooding when multiple matches exist:
  Tab advances to the longest shared prefix rather than dumping all matches
- SQL table name completion added after `FROM`, `JOIN`, and related keywords —
  loaded table names are now offered inline during query entry
- `_read_input` patching in tests no longer blocked by readline setup; completer
  initialisation is skipped entirely when `_input_fn` is injected (test mode)

### Known limitations
- Tab cycling through multiple matches (pressing Tab repeatedly to step through
  options) is not supported under `pyreadline3`; type enough characters to reach
  a unique prefix and Tab will complete it. Full cycling support planned when
  `prompt_toolkit` is evaluated as a readline replacement.
- Console prompt may not redraw automatically after the terminal scrolls; press
  Enter to refresh. This is a `pyreadline3` rendering limitation.

## [0.3.0] — 2026-08-28

### Added
- Wide-table display: columns auto-truncate with `…` to fit terminal width;
  proportional greedy budget algorithm with a floor of 4 chars per column
- Vertical output mode — two trigger mechanisms:
  - `\G` suffix immediately before `;` (e.g. `SELECT * FROM t\G;`)
  - Oracle-style hint `/*+ vertical_result(N) */` anywhere in the query,
    where N sets the display row cap independently of the query result set
- Tab autocomplete via `pyreadline3` (Windows) / `readline` (Linux/macOS):
  command names, table names after `:schema`/`:unload`/etc., file paths
  after `:load`, SQL keywords as fallback — degrades silently if unavailable
- `:unload all` — unload every loaded table in one command; reports count
  and lists any per-table failures without aborting the rest
- `:schema` now appends a Warnings section when load warnings exist
- Four-state `:load` output: clean / known errors only / DuckDB residual
  drops only / both — with actionable next-step hints per state
- `:tables` status column extended: `[!N]` known errors, `[!?]` residual
  drops only, `[!N +?]` both

### Changed
- CSV/PSV/TSV structural validation now scans the **full file** — the previous
  1,000-row cap meant errors beyond row 1,000 were silently ignored;
  `_errors_{name}` is now a complete record of all malformed rows
- Residual row-count cross-check added to every `:load`: compares raw line
  count against DuckDB-loaded count; any shortfall beyond known errors is
  stored as a warning with exact numbers (raw / loaded / known) for diagnosis

### Tests
- 105 passing (up from 67 in v0.2.1)
- New: `test_formatter_v3.py` (13), `test_completer.py` (11),
  `test_silent_errors.py` (7), additions to `test_commands_v2.py` (7)

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