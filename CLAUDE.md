# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`rpo` (Repository Participation Observer) is a Python library for analyzing git repository contribution data (blame, activity, punchcards). Python 3.13+ only. There is no python CLI — the command-line tool is the separate `rpo-cli` crate on crates.io.

The analysis engine is the [`rpo`](https://crates.io/crates/rpo) Rust crate, reached through a private pyo3 extension module (`rpo._rpo`). Python does no git walking of its own: the engine returns polars DataFrames over the Arrow C data interface, and the reports are polars transforms over those frames.

This is a maturin mixed Rust/Python project. Python source is under `python/rpo/`, the extension is built from `src/lib.rs`, and `version` is set literally in `pyproject.toml`.

## Commands

Dependencies are managed with `uv` (not pip). `Taskfile.yml` is the canonical runner (use `task`, not `make`):

- `task develop` — build the Rust extension and install it into the venv. Run this after any `src/lib.rs` change.
- `task build` — build a release wheel.
- `task test` — fast unit tests (excludes `slow` and `integration` markers). Uses `--env-file .env`.
- `task test_slow` — runs everything except integration (includes `slow`).
- `task integration` — runs `-m integration` tests (clones cpython if `LARGE_REPO_PATH` is not set — can be very slow).
- `task` (default) — runs `test`.

Single test: `uv run py.test tests/test_analyzer.py::test_name -v`.

CI has two workflows:

- `uv-python-app.yml` — on push/PR. Builds the extension (`maturin develop --release`), then runs pytest + ruff on linux. A separate `import-check` job builds a wheel on macOS and Windows and asserts the extension loads and analyzes a repository; the full suite does not run there.
- `python-publish.yml` — on published release. Builds wheels for linux (x86_64, aarch64), macOS (x86_64, aarch64), and windows x64, plus an sdist, then publishes to PyPI via trusted publishing. `workflow_dispatch` builds the matrix without publishing.

The extension is built with `abi3-py313`, so one wheel per platform covers 3.13 and every later 3.x. Match `uv run py.test -m 'not integration'`, `uv run ruff check -q`, and `uv run ruff format --check -q` before pushing. Pre-commit runs `deptry` and basic hygiene checks.

Coverage is always on (`addopts = -v --cov=rpo --cov-report=term-missing --cov-branch` in `pyproject.toml`).

## Architecture

Data flow: Rust engine (one walk) → polars `DataFrame` → report transform → optional Altair plot / file output.

Key modules in `python/rpo/`:

- `models.py` — the shared type vocabulary (`AggregateBy`, `IdentifyBy`, `Snapshots`) plus `group_column()`, which builds the `canonical_{aggregate_by}_{identify_by}` column name reports group on. Frames use the engine's vocabulary throughout: identities are the mailmap-aware `canonical_*` columns, file paths are `path`.
- `analyzer.py` — `RepoAnalyzer` is the main entrypoint. The constructor performs one walk via `_rpo.analyze()` and holds the frames; every report reads from them without touching the repository again. `_filtered(options)` is the shared read path for identity-level options (aliases, excluded users, limit) — path globs are applied by the engine at walk time, not here. Reports: `summary`, `revisions`, `contributor_report`, `file_report`, `blame`, `cumulative_blame`, `punchcard`, `bus_factor`, `file_timeline`.

  Two gotchas: reports must `.sort()` explicitly, since polars `group_by` does not guarantee order; and the engine's counts are unsigned, so anything computing a difference (e.g. `net`) must cast to `Int64` first or a net loss wraps to ~1.8e19.

  `blame(rev=...)` raises `NotImplementedError` for anything but HEAD — the engine's blame terminal is HEAD-only. Use `cumulative_blame` for historical data.
- `src/lib.rs` — the pyo3 extension (built as `rpo._rpo`). Exposes `commits`, `file_changes`, `blame`, `blame_over_time`, and `analyze`, each taking the walk options as keyword arguments. `RpoError` maps to a typed exception hierarchy; the GIL is released around every walk. Stubs live in `python/rpo/_rpo.pyi`.
- `plotting.py` — standalone chart helpers (`blame`, `cumulative_blame`, `punchcard`, `file_churn`). Each takes a report frame and an output path, writes an Altair PNG via `polars.DataFrame.plot`, and returns the path.

API convention, mirroring the Rust builder: walk options (globs, ignore_merges, ignore_bots, first_parent_only, snapshots) are constructor arguments on `RepoAnalyzer` and apply to every report. Report options (aggregate_by, identify_by, limit) are keyword arguments on the report methods. Reports return DataFrames and print nothing; plotting is a separate explicit call into `rpo.plotting`.

## Examples

`examples/` holds runnable scripts covering the public API; `examples/README.md` indexes them. They default to analyzing this checkout, so `python examples/01_quickstart.py` works with no arguments. Keep them working — they double as executable documentation.

## Testing Notes

- `tests/conftest.py` builds a synthetic `tmp_repo` (3 authors, file add/remove/truncate, one author email change mid-stream) and a `tmp_repo_analyzer` fixture. GitPython is still a dev dependency purely for building these fixtures — it is not a runtime dependency.
- `tests/test_bindings.py` covers the extension directly and deliberately mirrors `rpo-rust/rpo/tests/globs.rs`, so both language bindings agree on glob semantics.
- After changing anything in `src/lib.rs`, rebuild with `task develop` before running tests.
- `tests/integration/test_cpython_repository.py` clones cpython. Set `LARGE_REPO_PATH` to an existing local clone to avoid the download.
- Markers: `slow` and `integration` are registered in `pyproject.toml`; `conftest.py` auto-adds the `integration` marker to anything under `tests/integration/`.
