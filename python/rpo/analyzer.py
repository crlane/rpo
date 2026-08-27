"""Repository analysis, backed by the `rpo` Rust engine.

`RepoAnalyzer` mirrors the Rust `rpo::RepoAnalyzer` builder: walk options
are fixed when the analyzer is constructed, and the reports are polars
transforms over the frames that walk produced.

Reports return DataFrames and print nothing; formatting is the caller's
job.
"""

import logging
from pathlib import Path

import polars as pl
from polars import DataFrame

from . import _rpo
from .models import AggregateBy, IdentifyBy, Snapshots, group_column

logger = logging.getLogger(__name__)


class RepoAnalyzer:
    """Analyze a git repository's contribution history.

    Walk options are set once, here, and apply to every report:

    >>> ra = RepoAnalyzer("/path/to/repo", exclude_globs=["docs/**"])
    >>> ra.summary()
    >>> ra.contributor_report(identify_by="email")

    The walk happens eagerly in the constructor; reports read from the
    resulting frames without touching the repository again.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        snapshots: Snapshots = "head",
        revisions: list[str] | None = None,
        include_globs: list[str] | None = None,
        exclude_globs: list[str] | None = None,
        ignore_merges: bool = True,
        first_parent_only: bool = False,
        ignore_bots: bool = False,
    ):
        """
        Raises `NotARepositoryError` if `path` is not a git repository,
        and `InvalidGlobError` if a glob fails to parse.
        """
        self.path = str(path)
        self.name = Path(self.path).resolve().name
        self._walk_options = {
            "include_globs": include_globs,
            "exclude_globs": exclude_globs,
            "ignore_merges": ignore_merges,
            "first_parent_only": first_parent_only,
            "ignore_bots": ignore_bots,
        }
        self._analysis = _rpo.analyze(
            self.path, snapshots=snapshots, revisions=revisions, **self._walk_options
        )

    def __repr__(self) -> str:
        return (
            f"RepoAnalyzer({self.path!r}, commits={self.commits.height}, "
            f"file_changes={self.file_changes.height})"
        )

    # --- raw frames ----------------------------------------------------

    @property
    def commits(self) -> DataFrame:
        """One row per commit."""
        return self._analysis.commits

    @property
    def file_changes(self) -> DataFrame:
        """One row per (commit, file) touched."""
        return self._analysis.file_changes

    @property
    def blame(self) -> DataFrame | None:
        """One row per blame hunk at HEAD, or None if blame did not run."""
        return self._analysis.blame

    @property
    def blame_over_time(self) -> DataFrame | None:
        """Blame hunks per snapshot, if the analyzer was built with a
        cadence other than `head`."""
        return self._analysis.blame_over_time

    @property
    def skipped_files(self) -> list[str]:
        """Paths the engine could not blame (binary, too large, …)."""
        return self._analysis.skipped_files

    # --- reports -------------------------------------------------------

    def summary(
        self,
        *,
        aggregate_by: AggregateBy = "author",
        identify_by: IdentifyBy = "name",
    ) -> DataFrame:
        """One row: contributor, file, and commit counts plus the date range.

        Columns: `name`, `files`, `contributors`, `commits`,
        `first_commit`, `last_commit`.
        """
        group = group_column(aggregate_by, identify_by)
        return DataFrame(
            {
                "name": [self.name],
                "files": [self.file_changes["path"].n_unique()],
                "contributors": [self.file_changes[group].n_unique()],
                "commits": [self.file_changes["sha"].n_unique()],
                "first_commit": [self.commits["author_time"].min()],
                "last_commit": [self.commits["author_time"].max()],
            }
        )

    def contributor_report(
        self,
        *,
        aggregate_by: AggregateBy = "author",
        identify_by: IdentifyBy = "name",
        limit: int | None = None,
    ) -> DataFrame:
        """Per-contributor churn, most active first.

        Columns: the identity column, `commits`, `insertions`,
        `deletions`, `lines` (total churn), `net`.
        """
        group = group_column(aggregate_by, identify_by)
        report = (
            self.file_changes.group_by(group)
            .agg(
                pl.col("sha").n_unique().alias("commits"),
                pl.sum("insertions"),
                pl.sum("deletions"),
            )
            .with_columns(
                (pl.col("insertions") + pl.col("deletions")).alias("lines"),
                _net(),
            )
            .sort("lines", descending=True)
        )
        return report.head(limit) if limit else report

    def file_report(
        self,
        *,
        aggregate_by: AggregateBy = "author",
        identify_by: IdentifyBy = "name",
        limit: int | None = None,
    ) -> DataFrame:
        """Per-file churn, most changed first.

        Columns: `path`, `commits`, `contributors`, `insertions`,
        `deletions`, `lines`, `net`.
        """
        group = group_column(aggregate_by, identify_by)
        report = (
            self.file_changes.group_by("path")
            .agg(
                pl.col("sha").n_unique().alias("commits"),
                pl.col(group).n_unique().alias("contributors"),
                pl.sum("insertions"),
                pl.sum("deletions"),
            )
            .with_columns(
                (pl.col("insertions") + pl.col("deletions")).alias("lines"),
                _net(),
            )
            .sort("lines", descending=True)
        )
        return report.head(limit) if limit else report

    def blame_report(
        self,
        *,
        aggregate_by: AggregateBy = "author",
        identify_by: IdentifyBy = "name",
        limit: int | None = None,
    ) -> DataFrame:
        """Lines surviving at HEAD, per contributor.

        Columns: the identity column, `lines`, `files`.
        """
        group = group_column(aggregate_by, identify_by)
        if self.blame is None:
            return DataFrame()
        report = (
            self.blame.group_by(group)
            .agg(
                pl.sum("line_count").alias("lines"),
                pl.col("path").n_unique().alias("files"),
            )
            .sort("lines", descending=True)
        )
        return report.head(limit) if limit else report

    def cumulative_blame(
        self,
        *,
        aggregate_by: AggregateBy = "author",
        identify_by: IdentifyBy = "name",
        snapshots: Snapshots = "monthly",
    ) -> DataFrame:
        """Lines owned by each contributor at each point in time.

        One row per snapshot, one column per contributor — the shape a
        stacked area chart wants. Runs a second walk, since the snapshot
        cadence differs from the one the analyzer was built with.
        """
        group = group_column(aggregate_by, identify_by)
        raw = _rpo.blame_over_time(
            self.path, snapshots=snapshots, **self._walk_options
        )
        return (
            raw.group_by(["snapshot_time", group])
            .agg(pl.sum("line_count").alias("lines"))
            .pivot(
                group, index="snapshot_time", values="lines", aggregate_function="sum"
            )
            .sort("snapshot_time")
            .fill_null(0)
        )

    def file_timeline(self, *, snapshots: Snapshots = "monthly") -> DataFrame:
        """Line count per file at each snapshot.

        Columns: `snapshot_time`, `path`, `lines`.
        """
        raw = _rpo.blame_over_time(
            self.path, snapshots=snapshots, **self._walk_options
        )
        return (
            raw.group_by(["snapshot_time", "path"])
            .agg(pl.sum("line_count").alias("lines"))
            .sort(["snapshot_time", "path"])
        )

    def punchcard(
        self,
        identifier: str | None = None,
        *,
        aggregate_by: AggregateBy = "author",
        identify_by: IdentifyBy = "name",
    ) -> DataFrame:
        """Commit counts on a (day-of-week, hour) grid.

        Pass `identifier` to scope to one contributor; omit it for the
        whole repository. `day` is 1 (Monday) through 7 (Sunday).

        Columns: `day`, `hour`, `count`.
        """
        group = group_column(aggregate_by, identify_by)
        time_col = "commit_time" if aggregate_by == "committer" else "author_time"
        df = self.commits
        if identifier is not None:
            df = df.filter(pl.col(group) == identifier)
        return (
            df.select(
                pl.col(time_col).dt.weekday().alias("day"),
                pl.col(time_col).dt.hour().alias("hour"),
            )
            .group_by(["day", "hour"])
            .agg(pl.len().alias("count"))
            .sort(["day", "hour"])
        )


def _net() -> pl.Expr:
    """`insertions - deletions`, cast so a net loss stays negative.

    The engine's counts are unsigned; subtracting them directly wraps a
    net loss around to ~1.8e19.
    """
    return (
        pl.col("insertions").cast(pl.Int64) - pl.col("deletions").cast(pl.Int64)
    ).alias("net")
