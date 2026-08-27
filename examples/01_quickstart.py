"""The raw frames: one walk, four DataFrames.

    python examples/01_quickstart.py [repo-path]
"""

import polars as pl

import rpo
from _common import repo_from_argv

repo = repo_from_argv()
print(f"analyzing {repo}\n")

# One walk populates every frame. `snapshots` controls the blame-over-time
# cadence; "head" (the default) blames only the current tip.
analysis = rpo.analyze(repo)

print(analysis, "\n")

commits = analysis.commits
print(f"commits: {commits.height} rows x {commits.width} cols")
print(commits.select("short_sha", "canonical_author_name", "commit_time").head(5), "\n")

changes = analysis.file_changes
print(f"file_changes: {changes.height} rows")
print(changes.select("path", "insertions", "deletions").head(5), "\n")

if analysis.blame is not None:
    print(f"blame: {analysis.blame.height} hunks at HEAD\n")

# Datetimes cross the Rust/Python boundary as UTC milliseconds.
print("commit_time dtype:", commits.schema["commit_time"])

# The individual terminals are available too, when you only need one frame.
just_commits = rpo.commits(repo)
print("\nrpo.commits() gives the same frame:", just_commits.height == commits.height)

# Identities are canonicalized through .mailmap by the engine, so grouping
# on the canonical columns is always correct.
print(
    "\ntop authors:",
    commits.group_by("canonical_author_name")
    .agg(pl.len().alias("commits"))
    .sort("commits", descending=True)
    .head(3),
    sep="\n",
)
