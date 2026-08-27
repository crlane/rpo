"""How authorship shifts over the life of a repository.

    python examples/04_blame_over_time.py [repo-path]
"""

import polars as pl

import rpo
from _common import repo_from_argv

repo = repo_from_argv()

# The raw timeline: one row per (snapshot, hunk). Cadences are
# head | daily | weekly | monthly | tags | all.
timeline = rpo.blame_over_time(repo, snapshots="monthly")
print(f"{timeline.height} hunks across "
      f"{timeline['snapshot_time'].n_unique()} monthly snapshots\n")
print(timeline.select("snapshot_time", "path", "line_count").head(5), "\n")

# Snapshot at each tag instead — useful for per-release views.
tagged = rpo.blame_over_time(repo, snapshots="tags")
print(f"tag snapshots: {tagged['snapshot_time'].n_unique()}\n")

# Or at revisions you name yourself.
named = rpo.blame_over_time(repo, revisions=["HEAD"])
print(f"explicit revisions: {named['snapshot_time'].n_unique()}\n")

# The analyzer's cumulative_blame pivots this into chart-ready shape:
# one row per snapshot, one column per contributor.
ra = rpo.RepoAnalyzer(repo)
pivoted = ra.cumulative_blame(snapshots="monthly")
print("cumulative blame (wide):")
print(pivoted.tail(3), "\n")

# Which files carry the most surviving code at the latest snapshot?
latest = timeline.filter(
    pl.col("snapshot_time") == pl.col("snapshot_time").max()
)
print("largest files at the latest snapshot:")
print(
    latest.group_by("path")
    .agg(pl.sum("line_count").alias("lines"))
    .sort("lines", descending=True)
    .head(5)
)
