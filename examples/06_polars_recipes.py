"""Going beyond the built-in reports.

The reports are ordinary polars transforms over frames the engine
returns. When one does not fit, reach for the frames directly.

    python examples/06_polars_recipes.py [repo-path]
"""

import polars as pl
import rpo
from _common import repo_from_argv

repo = repo_from_argv()
ra = rpo.RepoAnalyzer(repo, exclude_globs=["**/*.lock"])
changes, commits = ra.file_changes, ra.commits

print("== churn by file extension ==")
print(
    changes.with_columns(pl.col("path").str.extract(r"\.([A-Za-z0-9]+)$").alias("ext"))
    .group_by("ext")
    .agg(
        pl.sum("insertions").alias("added"),
        pl.col("path").n_unique().alias("files"),
    )
    .sort("added", descending=True)
    .head(8),
    "\n",
)

print("== files that change together (co-change coupling) ==")
# Self-join file_changes on sha to find pairs touched by the same commit.
pairs = (
    changes.select("sha", "path")
    .join(changes.select("sha", other="path"), on="sha")
    .filter(pl.col("path") < pl.col("other"))
    .group_by("path", "other")
    .agg(pl.len().alias("together"))
    .sort("together", descending=True)
)
print(pairs.head(5), "\n")

print("== commit activity by month ==")
print(
    commits.group_by(pl.col("commit_time").dt.truncate("1mo").alias("month"))
    .agg(pl.len().alias("commits"))
    .sort("month")
    .tail(6),
    "\n",
)

print("== files nobody has touched recently ==")
print(
    changes.join(commits.select("sha", "commit_time"), on="sha")
    .group_by("path")
    .agg(pl.max("commit_time").alias("last_touched"))
    .sort("last_touched")
    .head(5),
    "\n",
)

print("== knowledge concentration: top owner's share per file ==")
blame = ra.blame
if blame is not None:
    per_file = blame.group_by("path", "canonical_author_name").agg(
        pl.sum("line_count").alias("lines")
    )
    totals = per_file.group_by("path").agg(pl.sum("lines").alias("total"))
    print(
        per_file.join(totals, on="path")
        .with_columns((pl.col("lines") / pl.col("total")).alias("share"))
        .sort("share", descending=True)
        .select("path", "canonical_author_name", "share")
        .head(5)
    )
