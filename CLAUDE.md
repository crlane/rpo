# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`rpo` (Repository Participation Observer) is a CLI + Python library for analyzing git repository contribution data (blame, activity, bus factor, punchcards). Python 3.13+ only.

The analysis engine is the [`rpo`](https://crates.io/crates/rpo) Rust crate, reached through a private pyo3 extension module (`rpo._rpo`). Python does no git walking of its own: the engine returns polars DataFrames over the Arrow C data interface, and the reports are polars transforms over those frames.

This is a maturin mixed Rust/Python project. Python source is under `python/rpo/`, the extension is built from `src/lib.rs`, and `version` is set literally in `pyproject.toml`.

## Commands

Dependencies are managed with `uv` (not pip). `Taskfile.yml` is the canonical runner (use `task`, not `make`):

- `task develop` — build the Rust extension and install it into the venv. Run this after any `src/lib.rs` change.
- `task build` — build a release wheel.
- `task test` — fast unit tests (excludes `slow` and `integration` markers). Uses `--env-file .env`.
- `task test_slow` — runs everything except integration (includes `slow`).
- `task integration` — runs `-m integration` tests (clones cpython if `LARGE_REPO_PATH` is not set — can be very slow).
- `task test_cli` — end-to-end CLI smoke test via `test_cli.sh`. Expects `REPO` env var pointing at an adjacent git repo (default `../requests`).
- `task` (default) — runs `test` + `test_cli`.

Single test: `uv run py.test tests/test_analyzer.py::test_name -v`.

CI (`.github/workflows/uv-python-app.yml`) runs `uv run py.test -m 'not integration'` plus `uv run ruff check -q` and `uv run ruff format -q`. Match this before pushing. Pre-commit runs `deptry` (with `--ignore DEP001`) and basic hygiene checks.

Coverage is always on (`addopts = -v --cov=rpo --cov-report=term-missing --cov-branch` in `pyproject.toml`).

## Architecture

Data flow: Rust engine (one walk) → polars `DataFrame` → report transform → optional Altair plot / file output.

Key modules in `python/rpo/`:

- `main.py` — Click CLI entrypoint (`rpo = rpo.main:cli`). Uses `ClickAliasedGroup` and `pydanclick.from_pydantic` to derive CLI flags directly from pydantic option models. Each subcommand stacks `@data_options`, `@file_options`/`@plot_options` decorators to build a combined `*CmdOptions` model that it hands to the analyzer. A config file (`~/.config/rpo/config.json` or `./.rpo.config.json`) can override any `GitOptions` field at startup.
- `models.py` — All pydantic option models. `DataSelectionOptions` is the core shared base. Note the frames use the engine's vocabulary: reports group on `canonical_{aggregate_by}_{identify_by}` (mailmap-aware, built by the engine), and file reports key on `path`, not `filename`. The `_canonical()` helper in `analyzer.py` maps an options object onto that column name.
- `analyzer.py` — `RepoAnalyzer` is the main entrypoint. The constructor performs one walk via `_rpo.analyze()` and holds the frames; every report reads from them without touching the repository again. `_filtered(options)` is the shared read path for identity-level options (aliases, excluded users, limit) — path globs are applied by the engine at walk time, not here. Reports: `summary`, `revisions`, `contributor_report`, `file_report`, `blame`, `cumulative_blame`, `punchcard`, `bus_factor`, `file_timeline`.

  Two gotchas: reports must `.sort()` explicitly, since polars `group_by` does not guarantee order; and the engine's counts are unsigned, so anything computing a difference (e.g. `net`) must cast to `Int64` first or a net loss wraps to ~1.8e19.

  `blame(rev=...)` raises `NotImplementedError` for anything but HEAD — the engine's blame terminal is HEAD-only. Use `cumulative_blame` for historical data.
- `src/lib.rs` — the pyo3 extension (built as `rpo._rpo`). Exposes `commits`, `file_changes`, `blame`, `blame_over_time`, and `analyze`, each taking the walk options as keyword arguments. `RpoError` maps to a typed exception hierarchy; the GIL is released around every walk. Stubs live in `python/rpo/_rpo.pyi`.
- `plotting.py` — `Plotter` dispatches on `SupportedPlotType` (`"blame" | "cumulative_blame" | "punchcard"`) and writes Altair PNGs via `polars.DataFrame.plot` to `PlotOptions.img_location`.
- `types.py`, `exceptions.py` — small shared types / exception classes.
- `server.py` — empty placeholder.

Options plumbing convention: analyzer methods accept a specific `*CmdOptions` model (e.g. `BlameCmdOptions`) that multiply-inherits `DataSelectionOptions` and an output mixin. CLI commands build these by spreading `.model_dump()` of the decorator-produced sub-models. When adding a new command, follow this pattern rather than adding loose `click.option` decorators.

## Testing Notes

- `tests/conftest.py` builds a synthetic `tmp_repo` (3 authors, file add/remove/truncate, one author email change mid-stream) and a `tmp_repo_analyzer` fixture. GitPython is still a dev dependency purely for building these fixtures — it is not a runtime dependency.
- `tests/test_bindings.py` covers the extension directly and deliberately mirrors `rpo-rust/rpo/tests/globs.rs`, so both language bindings agree on glob semantics.
- After changing anything in `src/lib.rs`, rebuild with `task develop` before running tests.
- `tests/integration/test_cpython_repository.py` clones cpython. Set `LARGE_REPO_PATH` to an existing local clone to avoid the download.
- Markers: `slow` and `integration` are registered in `pyproject.toml`; `conftest.py` auto-adds the `integration` marker to anything under `tests/integration/`.
