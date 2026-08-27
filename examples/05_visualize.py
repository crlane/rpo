"""Charts from the report frames.

Plotting is explicit: reports return DataFrames, and you hand one to a
plotting helper when you want a picture. Writes PNGs to ./img.

    python examples/05_visualize.py [repo-path]
"""

from pathlib import Path

import rpo
from _common import repo_from_argv

repo = repo_from_argv()
out = Path("img")

ra = rpo.RepoAnalyzer(repo, exclude_globs=["**/*.lock", "**/*.min.js"])

# Who owns the code that survives at HEAD.
print(rpo.plotting.blame(
    ra.blame_report(limit=15),
    out / "blame.png",
    title=f"{ra.name}: lines owned at HEAD",
))

# How that ownership built up over time (stacked area).
print(rpo.plotting.cumulative_blame(
    ra.cumulative_blame(snapshots="monthly"),
    out / "cumulative_blame.png",
    title=f"{ra.name}: cumulative blame",
))

# When commits land, as a day/hour bubble grid.
print(rpo.plotting.punchcard(
    ra.punchcard(),
    out / "punchcard.png",
    title=f"{ra.name}: commit punchcard",
))

# Which files churn most.
print(rpo.plotting.file_churn(
    ra.file_report(),
    out / "file_churn.png",
    top=15,
    title=f"{ra.name}: most-changed files",
))

# The helpers are thin. For anything custom, go straight to Altair via
# polars' .plot accessor on any report frame:
chart = (
    ra.contributor_report(limit=10)
    .plot.bar(x="commits:Q", y="canonical_author_name:N")
    .properties(title="Commits per contributor")
)
chart.save(out / "custom.png", ppi=200)
print(out / "custom.png")
