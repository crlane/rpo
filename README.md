# RPO: Repository Participation Observer

[![Python application](https://github.com/crlane/rpo/actions/workflows/uv-python-app.yml/badge.svg)](https://github.com/crlane/rpo/actions/workflows/uv-python-app.yml)

A Python library to help you analyze and visualize Git repositories. Ever wondered who has most contributions? How participation has changed over time? What are the hotspots in your code that change frequently? Who has the highest bus factor? `rpo` can help.

> NOTE: This is alpha software under active development. There will be breaking changes.

## Install

```bash
pip install rpo
```

Wheels bundle a compiled Rust extension, so there is no toolchain to set
up and no `git` binary is shelled out to.

## Usage

```python
import rpo

ra = rpo.RepoAnalyzer("./path/to/git_repo")

ra.summary()
ra.contributor_report(identify_by="email", limit=10)
ra.file_report(limit=10)
ra.blame_report()
ra.punchcard()
```

Walk options are set once, on the analyzer, and apply to every report —
mirroring the Rust builder:

```python
ra = rpo.RepoAnalyzer(
    path,
    exclude_globs=["docs/**", "**/*.lock"],
    ignore_bots=True,
    first_parent_only=False,
)
```

Report options are keyword arguments:

```python
ra.contributor_report(aggregate_by="committer", identify_by="email", limit=5)
```

Reports return [polars] DataFrames and print nothing, so they compose
with your own analysis:

```python
import polars as pl

(ra.file_report()
   .filter(pl.col("contributors") == 1)
   .sort("lines", descending=True))
```

### The raw frames

For anything the built-in reports do not cover, take the frames
directly. `commits`, `file_changes`, `blame`, and `blame_over_time`
mirror the Rust library's terminals:

```python
analysis = rpo.analyze(path, snapshots="monthly")
analysis.commits          # one row per commit
analysis.file_changes     # one row per (commit, file)
analysis.blame            # per-line authorship at HEAD
analysis.blame_over_time  # ...at each snapshot
```

Identities are canonicalized through `.mailmap` by the engine, so
reports group on `canonical_author_name`, `canonical_committer_email`,
and so on. File paths are `path`; datetimes are UTC milliseconds.

### Charts

Plotting is an explicit call, never a side effect of running a report:

```python
rpo.plotting.blame(ra.blame_report(limit=15), "img/blame.png")
rpo.plotting.cumulative_blame(ra.cumulative_blame(), "img/cblame.png")
rpo.plotting.punchcard(ra.punchcard(), "img/punchcard.png")
```

Any report frame also works directly with Altair through polars'
`.plot` accessor.

### Errors

Failures from the engine surface as typed exceptions, all subclassing
`rpo.RpoError`: `NotARepositoryError`, `InvalidGlobError`,
`RevisionNotFoundError`.

## Examples

Runnable scripts live in [`examples/`](./examples), covering the frames,
every report, filtering, blame over time, charts, and custom polars
recipes. They default to analyzing this checkout:

```bash
python examples/01_quickstart.py
python examples/02_reports.py ~/src/some-other-repo
```

## Command line

There is no python CLI. The command-line tool is
[`rpo-cli`](https://crates.io/crates/rpo-cli), installed separately:

```bash
cargo install rpo-cli
rpo summary -r ./path/to/repo
```

## Features
- [ ] Automatically generate aliases that refer to the same person
- [x] Support analyzing by glob
- [x] Support excluding by glob
- [x] Produce blame charts
- [x] Optionally ignore merge commits
- [ ] Optionally ignore whitespace (awaiting upstream gix support)
- [ ] Identify major refactorings
- [x] Fast execution, even on giant repositories (the engine is Rust)


## Performance

The goal is for the library to work even on the largest libraries. In general, the performance is proportional to the number of authors, commits, and files being considered in the aggregations.

The authors regularly [test](./tests/integration/test_cpython_repository.py) using the [cpython repository](https://github.com/python/cpython), which contains over 1,000,000 objects. That takes a while.

> TODO: Performance graphs

## Similar Projects and Inspiration

- [GitPandas](https://github.com/wdm0006/git-pandas)
- [git-truck](https://github.com/git-truck)
- [busfactor](https://github.com/SOM-Research/busfactor)
- [bus-factor-explorer](https://github.com/JetBrains-Research/bus-factor-explorer)
- [git-of-theseus](https://github.com/erikbern/git-of-theseus)
- [hercules](https://github.com/src-d/hercules)

## References

### Git Commands

These are useful for validating results reported here. The git man pages for various commands is helpful reading.

All the files edited in a revision
```bash
git diff-tree --no-commit-id --name-only HEAD~1 -r
```

All the files _present_ at a particular revision
```bash
git ls-tree -rlt HEAD
```

All commits reachable from a revision
```bash
git rev-list HEAD --count
```

Count all commits reachable from a revision
```bash
git rev-list HEAD --count
```

All commits that touch a particular object (tree in this case)
```bash
git rev-list HEAD img
```

All files at each commit
```bash
git rev-list HEAD | xargs -r -I % git ls-tree -rt --name-only %
```

```bash
git cat-file --batch-all-objects --batch-check --unordered
```

```bash
git rev-list --all --objects --filter=object:type=blob HEAD | git cat-file --batch-check="%(objectname) %(objecttype) %(rest) %(deltabase)"
```

```bash
git log --follow --pretty=format:%H -- FILE
```

[polars]: https://pola.rs
