# Examples

Runnable scripts covering the `rpo` python API. Each takes an optional
repository path and defaults to this checkout, so they work with no
arguments:

```sh
python examples/01_quickstart.py
python examples/01_quickstart.py ~/src/some-other-repo
```

They import a local `_common` helper, so run them from the repository
root as shown (not with `python -m`).

| Script | Covers |
|---|---|
| `01_quickstart.py` | `analyze()` and the individual frame terminals; dtypes across the boundary |
| `02_reports.py` | `RepoAnalyzer` and every built-in report |
| `03_filtering.py` | Path globs, merge/bot/first-parent options, typed errors |
| `04_blame_over_time.py` | Snapshot cadences and the authorship timeline |
| `05_visualize.py` | Charts via `rpo.plotting`, plus a hand-rolled Altair chart |
| `06_polars_recipes.py` | Custom analysis straight on the frames |

## The shape of the API

Walk options are fixed when the analyzer is built and apply to every
report — this mirrors the Rust builder:

```python
ra = rpo.RepoAnalyzer(path, exclude_globs=["docs/**"], ignore_bots=True)
```

Report options are keyword arguments:

```python
ra.contributor_report(aggregate_by="committer", identify_by="email", limit=10)
```

Reports return polars DataFrames and print nothing. Plotting is a
separate, explicit call.

## Column names

Frames use the engine's vocabulary. Identities are canonicalized through
`.mailmap`, so reports group on `canonical_author_name`,
`canonical_committer_email`, and so on — not the raw `author_name`.
File paths are `path`. Datetimes are UTC milliseconds.

`rpo.group_column("author", "email")` builds the column name if you need
it dynamically.
