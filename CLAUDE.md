# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`rpo` (Repository Participation Observer) is a CLI + Python library for analyzing git repository contribution data (blame, activity, bus factor, punchcards). Python 3.13+ only. Packaged with hatchling; version lives in `src/rpo/__init__.py` (`__version__`) and is consumed via `tool.hatch.version`.

## Commands

Dependencies are managed with `uv` (not pip). `Taskfile.yml` is the canonical runner (use `task`, not `make`):

- `task test` — fast unit tests (excludes `slow` and `integration` markers). Uses `--env-file .env`.
- `task test_slow` — runs everything except integration (includes `slow`).
- `task integration` — runs `-m integration` tests (clones cpython if `LARGE_REPO_PATH` is not set — can be very slow).
- `task test_cli` — end-to-end CLI smoke test via `test_cli.sh`. Expects `REPO` env var pointing at an adjacent git repo (default `../requests`).
- `task` (default) — runs `test` + `test_cli`.

Single test: `uv run py.test tests/test_analyzer.py::test_name -v`.

CI (`.github/workflows/uv-python-app.yml`) runs `uv run py.test -m 'not integration'` plus `uv run ruff check -q` and `uv run ruff format -q`. Match this before pushing. Pre-commit runs `deptry` (with `--ignore DEP001`) and basic hygiene checks.

Coverage is always on (`addopts = -v --cov=rpo --cov-report=term-missing --cov-branch` in `pyproject.toml`) and configured for multiprocess collection in `.coveragerc` — the cumulative-blame test path spawns a `multiprocessing.Pool`, and `.coverage.*` files are expected artifacts.

## Architecture

Data flow: `git.Repo` → `FileChangeCommitRecord` (pydantic) → DuckDB → polars `DataFrame` → optional Altair plot / file output.

Key modules in `src/rpo/`:

- `main.py` — Click CLI entrypoint (`rpo = rpo.main:cli`). Uses `ClickAliasedGroup` and `pydanclick.from_pydantic` to derive CLI flags directly from pydantic option models. Each subcommand stacks `@data_options`, `@file_options`/`@plot_options` decorators to build a combined `*CmdOptions` model that it hands to the analyzer. A config file (`~/.config/rpo/config.json` or `./.rpo.config.json`) can override any `GitOptions` field at startup.
- `models.py` — All pydantic option models. `DataSelectionOptions` is the core shared base: `group_by_key` = `f"{aggregate_by}_{identify_by}"` (e.g. `author_email`) is the column analyzers group on; `sort_key` translates `sort_by` into a polars column/selector; `glob_filter_expr` produces the include/exclude/generated-files filter list that analyzer queries apply. `FileChangeCommitRecord.from_git` is the bridge from `git.Commit` to a flat record — when `by_file=True` it yields one record per changed file with per-file `insertions`/`deletions`/`lines`/`is_binary`.
- `analyzer.py` — `RepoAnalyzer` is the main entrypoint for library users. `self.revs` lazily walks commits (respecting `ignore_merges`) into DuckDB via `DB.insert_file_changes` and caches the resulting polars frame; subsequent runs pick up from the last stored sha (`DB.get_latest_change_tuple`). `filtered_revs(options)` is the canonical read path — it applies aliases, excluded users, glob filters, and sort/limit. Reports: `summary`, `revisions`, `contributor_report`, `file_report`, `blame`, `cumulative_blame`, `punchcard`, `bus_factor`. `cumulative_blame` fans blame-per-revision out across a `multiprocessing.Pool` (size = `cpu_count()`); the pool is set up manually rather than via a context manager **because a context manager kills subprocesses in a way that breaks coverage collection** — don't "fix" this.
- `db.py` — DuckDB wrapper. Two tables: `file_changes` (one row per (commit, file)) and `sha_files`. A module-level `gconnection` is reused across instances; `in_memory=True` keeps everything in `:memory:`, otherwise data is persisted to `$TMPDIR/rpo-data/{repo_name}.ddb`. `_check_group_by` allowlists group-by columns because DuckDB parameters can't be used for `GROUP BY` clauses — keep that allowlist in sync with any new identifier columns to avoid SQL injection.
- `plotting.py` — `Plotter` dispatches on `SupportedPlotType` (`"blame" | "cumulative_blame" | "punchcard"`) and writes Altair PNGs via `polars.DataFrame.plot` to `PlotOptions.img_location`.
- `types.py`, `exceptions.py` — small shared types / exception classes.
- `server.py` — empty placeholder.

Options plumbing convention: analyzer methods accept a specific `*CmdOptions` model (e.g. `BlameCmdOptions`) that multiply-inherits `DataSelectionOptions` and an output mixin. CLI commands build these by spreading `.model_dump()` of the decorator-produced sub-models. When adding a new command, follow this pattern rather than adding loose `click.option` decorators.

## Testing Notes

- `tests/conftest.py` builds a synthetic `tmp_repo` (3 authors, file add/remove/truncate, one author email change mid-stream) and a `tmp_repo_analyzer` fixture (`in_memory=True`). Use these for unit tests rather than mocking `git.Repo`.
- `tests/integration/test_cpython_repository.py` clones cpython. Set `LARGE_REPO_PATH` to an existing local clone to avoid the download.
- Markers: `slow` and `integration` are registered in `pyproject.toml`; `conftest.py` auto-adds the `integration` marker to anything under `tests/integration/`.
