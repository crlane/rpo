"""Repository analysis, backed by the `rpo` Rust engine.

`RepoAnalyzer` walks a repository once via the Rust extension and holds
the resulting polars frames. Reports are polars transforms over those
frames.

The Rust engine supplies canonical identity columns
(`canonical_{author,committer}_{name,email}`) that already respect
`.mailmap`, so the frames are grouped on those directly.
"""

import logging
from pathlib import Path
from typing import Any

import polars as pl
import polars.selectors as cs
from polars import DataFrame

from . import _rpo
from .models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    BusFactorCmdOptions,
    GitOptions,
    OutputOptions,
    PunchcardCmdOptions,
    RevisionsCmdOptions,
    SummaryCmdOptions,
)
from .plotting import Plotter
from .types import SupportedPlotType

logger = logging.getLogger(__name__)

type AnyCmdOptions = (
    SummaryCmdOptions
    | BlameCmdOptions
    | PunchcardCmdOptions
    | RevisionsCmdOptions
    | ActivityReportCmdOptions
    | BusFactorCmdOptions
)


def _canonical(options: AnyCmdOptions) -> str:
    """The Rust frame column that `options` groups by.

    The python vocabulary is `{aggregate_by}_{identify_by}` (e.g.
    `author_email`); the engine's canonicalized equivalent is
    `canonical_author_email`.
    """
    return f"canonical_{options.aggregate_by}_{options.identify_by}"


class RepoAnalyzer:
    """Analyze a git repository's contribution history.

    One walk populates every frame; reports read from them without
    touching the repository again.
    """

    def __init__(
        self,
        options: GitOptions | None = None,
        path: str | Path | None = None,
        repo: Any | None = None,
        **kwargs: Any,
    ):
        """
        `path` is the repository to analyze. `repo` accepts any object
        exposing a `working_dir` (e.g. a `git.Repo`) and is supported so
        callers that already hold one do not have to unwrap it.
        """
        self.options = options or GitOptions()
        if path is not None:
            self.options.path = Path(path)
        elif repo is not None:
            working_dir = getattr(repo, "working_dir", None)
            if working_dir is None:
                raise ValueError("`repo` must expose a `working_dir` attribute")
            self.options.path = Path(str(working_dir))
        if self.options.path is None:
            raise ValueError("Must supply either a repository path or a repo object")

        self.path = str(self.options.path)
        self.name = self.options.path.name

        # Raises NotARepositoryError if the path is not a git repository.
        self._analysis = _rpo.analyze(
            self.path,
            snapshots="head",
            ignore_merges=self.options.ignore_merges,
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
    def commit_count(self) -> int:
        return self.commits.height

    def _filtered(self, options: AnyCmdOptions, ignore_limit: bool = False) -> DataFrame:
        """Apply the identity-level options shared by every report.

        Path globs are applied by the engine at walk time, so only the
        alias/exclude/limit handling remains here.
        """
        group = _canonical(options)
        df = self.file_changes
        if options.aliases:
            df = df.with_columns(pl.col(group).replace(options.aliases))
        if options.exclude_users:
            df = df.filter(pl.col(group).is_in(options.exclude_users).not_())

        if not ignore_limit and options.limit and options.limit > 0:
            by = options.sort_key
            df = (
                df.bottom_k(options.limit, by=by)
                if options.sort_descending
                else df.top_k(options.limit, by=by)
            )
        return df

    def _output(
        self,
        output_df: DataFrame,
        options: AnyCmdOptions,
        plot_df: DataFrame | None = None,
        plot_type: SupportedPlotType | None = None,
        **kwargs: Any,
    ):
        # Command options are flat: they carry `stdout`, `visualize`, and
        # `img_location` directly rather than nesting an OutputOptions.
        output_options = OutputOptions()
        for k, v in options.model_dump().items():
            if hasattr(output_options, k):
                setattr(output_options, k, v)

        if output_options.stdout:
            print(output_df)
        if output_options.visualize and plot_type is not None:
            plot_df = plot_df if plot_df is not None else output_df
            Plotter(plot_df, output_options, plot_type, **kwargs).plot()

    # --- reports -------------------------------------------------------

    def summary(self, options: SummaryCmdOptions) -> DataFrame:
        """Counts of files, contributors, and commits."""
        group = _canonical(options)
        changes = self._filtered(options)
        commits = self.commits
        summary_df = DataFrame(
            {
                "name": [self.name],
                "files": [changes["path"].n_unique()],
                "contributors": [changes[group].n_unique()],
                "commits": [changes["sha"].n_unique()],
                "first_commit": [commits["author_time"].min()],
                "last_commit": [commits["author_time"].max()],
            }
        )
        self._output(summary_df, options)
        return summary_df

    def revisions(self, options: RevisionsCmdOptions) -> DataFrame:
        """One row per commit, after identity filtering."""
        group = _canonical(options)
        df = self.commits
        if options.aliases:
            df = df.with_columns(pl.col(group).replace(options.aliases))
        if options.exclude_users:
            df = df.filter(pl.col(group).is_in(options.exclude_users).not_())
        self._output(df, options)
        return df

    def contributor_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        """Per-contributor insertions, deletions, and net lines."""
        group = _canonical(options)
        report_df = (
            self._filtered(options)
            .group_by(group)
            .agg(pl.sum("insertions"), pl.sum("deletions"))
            .with_columns(
                (pl.col("insertions") + pl.col("deletions")).alias("lines"),
                # Cast before subtracting: the engine's counts are
                # unsigned, so a net loss would otherwise wrap around.
                (
                    pl.col("insertions").cast(pl.Int64)
                    - pl.col("deletions").cast(pl.Int64)
                ).alias("net"),
            )
            .sort(group)
        )
        self._output(report_df, options)
        return report_df

    def file_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        """Per-file insertions, deletions, and net lines."""
        report_df = (
            self._filtered(options)
            .group_by("path")
            .agg(pl.sum("insertions"), pl.sum("deletions"))
            .with_columns(
                (pl.col("insertions") + pl.col("deletions")).alias("lines"),
                # Cast before subtracting: the engine's counts are
                # unsigned, so a net loss would otherwise wrap around.
                (
                    pl.col("insertions").cast(pl.Int64)
                    - pl.col("deletions").cast(pl.Int64)
                ).alias("net"),
            )
            .sort("path")
        )
        self._output(report_df, options)
        return report_df

    def blame(
        self,
        options: BlameCmdOptions,
        rev: str | None = None,
        data_field: str = "lines",
    ) -> DataFrame:
        """Lines at HEAD attributed to each contributor.

        `rev` is accepted for CLI compatibility but only HEAD is
        supported: the engine's blame terminal is HEAD-only. Passing
        anything else raises rather than silently reporting HEAD.
        """
        if rev is not None and rev not in ("HEAD", "head"):
            raise NotImplementedError(
                f"blame at revision {rev!r} is not supported yet; "
                "the engine's blame is HEAD-only. Use cumulative_blame "
                "with snapshots for historical data."
            )
        group = _canonical(options)
        blame_df = self._analysis.blame
        if blame_df is None:
            return DataFrame()
        report_df = (
            blame_df.group_by(group)
            .agg(pl.sum("line_count").alias("lines"))
            .sort("lines", descending=True)
        )
        self._output(
            report_df,
            options,
            plot_type="blame",
            title=f"{self.name} Blame at HEAD",
            x="lines:Q",
            y=group,
            filename=f"{self.name}_blame_by_{group}",
        )
        return report_df

    def cumulative_blame(self, options: BlameCmdOptions) -> DataFrame:
        """Lines attributed to each contributor at each snapshot in time."""
        group = _canonical(options)
        raw = _rpo.blame_over_time(
            self.path,
            snapshots=getattr(options, "snapshots", None) or "monthly",
            ignore_merges=self.options.ignore_merges,
        )
        pivot_df = (
            raw.group_by(["snapshot_time", group])
            .agg(pl.sum("line_count").alias("lines"))
            .pivot(group, index="snapshot_time", values="lines", aggregate_function="sum")
            .sort(cs.temporal())
            .fill_null(0)
        )
        self._output(
            pivot_df,
            options,
            plot_df=raw,
            plot_type="cumulative_blame",
            x="snapshot_time:T",
            y="sum(line_count):Q",
            color=f"{group}:N",
            title=f"{self.name} Cumulative Blame",
            filename=f"{self.name}_cumulative_blame_by_{group}",
        )
        return pivot_df

    def bus_factor(self, options: BusFactorCmdOptions) -> DataFrame:
        """Smallest set of contributors owning most of the codebase.

        Ranks contributors by lines owned at HEAD and counts how many
        are needed to cross `options.threshold` percent of the total.
        """
        group = _canonical(options)
        blame_df = self._analysis.blame
        if blame_df is None:
            return DataFrame()

        threshold = getattr(options, "threshold", 50) / 100
        owned = (
            blame_df.group_by(group)
            .agg(pl.sum("line_count").alias("lines"))
            .sort("lines", descending=True)
        )
        total = owned["lines"].sum()
        if not total:
            return DataFrame({"bus_factor": [0], "contributors": [0]})

        cumulative = owned.with_columns(
            (pl.col("lines").cum_sum() / total).alias("share")
        )
        # +1 because we need the contributor that crosses the threshold.
        factor = int((cumulative["share"] < threshold).sum()) + 1
        report_df = DataFrame(
            {"bus_factor": [factor], "contributors": [owned.height]}
        )
        self._output(report_df, options)
        return report_df

    def punchcard(self, options: PunchcardCmdOptions) -> DataFrame:
        """Commit activity by day and hour for one contributor."""
        group = _canonical(options)
        time_col = (
            "commit_time" if options.aggregate_by == "committer" else "author_time"
        )
        df = (
            self.commits.filter(pl.col(group) == options.identifier)
            .select(
                pl.col(time_col).alias("time"),
                pl.col(time_col).dt.weekday().alias("day"),
                pl.col(time_col).dt.hour().alias("hour"),
            )
            .group_by(["day", "hour"])
            .agg(pl.len().alias("count"))
            .sort(["day", "hour"])
        )
        self._output(
            df,
            options,
            plot_df=df,
            plot_type="punchcard",
            x="hour:O",
            y="day:O",
            color="sum(count):Q",
            size="sum(count):Q",
            title=f"{options.identifier} Punchcard".title(),
            filename=f"{self.name}_punchcard",
        )
        return df

    def file_timeline(self, options: ActivityReportCmdOptions) -> DataFrame:
        """Per-file line counts at each snapshot in time."""
        raw = _rpo.blame_over_time(
            self.path,
            snapshots=getattr(options, "snapshots", None) or "monthly",
            ignore_merges=self.options.ignore_merges,
        )
        df = (
            raw.group_by(["snapshot_time", "path"])
            .agg(pl.sum("line_count").alias("lines"))
            .sort(["snapshot_time", "path"])
        )
        self._output(df, options)
        return df
