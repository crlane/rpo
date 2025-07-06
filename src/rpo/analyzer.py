import functools
import logging
import time
from collections.abc import Iterator
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any
from urllib.parse import quote

import polars as pl
import polars.selectors as cs
from git import Actor
from git.repo import Repo
from git.repo.base import BlameEntry
from git.types import Commit_ish
from polars import DataFrame

from .db import DB
from .models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    BusFactorCmdOptions,
    FileChangeCommitRecord,
    GitOptions,
    OutputOptions,
    PunchcardCmdOptions,
    RevisionsCmdOptions,
    SummaryCmdOptions,
)
from .plotting import Plotter
from .types import SupportedPlotType

logger = logging.getLogger(__name__)

LARGE_THRESHOLD = 10_000

max_cpu_count = cpu_count() or 4

type AnyCmdOptions = (
    SummaryCmdOptions
    | BlameCmdOptions
    | PunchcardCmdOptions
    | RevisionsCmdOptions
    | ActivityReportCmdOptions
    | BusFactorCmdOptions
)


class RepoAnalyzer:
    """
    `RepoAnalyzer` connects `git.repo.Repo` to polars dataframes
    for on demand analysis.
    """

    def __init__(
        self,
        options: GitOptions | None = None,
        repo: Repo | None = None,
        in_memory: bool = False,
    ):
        self.options = options or GitOptions()
        if self.options.path is None and repo is None:
            raise ValueError("Must supply either repository path or a git.Repo object")

        if repo is not None:
            self.repo = repo
            self.options.path = Path(repo.common_dir).parent
        elif (self.options.path / ".git").exists():
            self.repo = Repo(self.options.path)
        else:
            raise ValueError("Specified path does not contain '.git' directory")

        if self.repo.bare:
            raise ValueError(
                "Repository has no commits! Please check the path and/or unstage any changes"
            )
        elif self.repo.is_dirty():
            logger.warning("Repository has uncommitted changes! Proceed with caution.")

        self._commit_count = None

        self._revs = None

        self.name = self.options.path.name
        self._db = DB(name=self.name, in_memory=in_memory, initialize=True)

    @functools.cache
    def _file_names_at_rev(self, rev: str) -> pl.Series:
        raw = self.repo.git.ls_tree("-r", "--name-only", rev)
        vals = raw.strip().split("\n")
        return pl.Series(name="filename", values=vals)

    @property
    def commit_count(self):
        if self._commit_count is None:
            self._commit_count = self.repo.head.commit.count()
        return self._commit_count

    @property
    def revs(self):
        """The git revisions property."""
        _, sha = self._db.get_latest_change_tuple()
        if self._revs is None:
            revs: list[FileChangeCommitRecord] = []
            rev_spec = (
                self.repo.head.commit.hexsha
                if sha is None
                else f"{sha}...{self.repo.head.commit.hexsha}"
            )
            for c in self.repo.iter_commits(
                rev_spec, no_merges=self.options.ignore_merges
            ):
                revs.extend(FileChangeCommitRecord.from_git(c, self.name, by_file=True))

            self._revs = self._db.insert_file_changes(revs)

        assert self._revs is not None
        count = self._revs.unique("sha").height

        assert count == self._db.change_count(), (
            "Mismatch of database and dataframe sha counts"
        )
        if count != self.commit_count:
            logger.warning(
                f"Excluding {self.commit_count - count} commits due to settings"
            )
        return self._revs

    def filtered_revs(self, options: AnyCmdOptions, ignore_limit=False):
        df = (
            self.revs.with_columns(
                pl.col(options.group_by_key).replace(options.aliases)
            )
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
            .filter(
                options.glob_filter_expr(
                    self.revs["filename"],
                )
            )
        )
        if not ignore_limit:
            if not options.limit or options.limit <= 0:
                df = df.sort(by=options.sort_key)
            elif options.sort_descending:
                df = df.bottom_k(options.limit, by=options.sort_key)
            else:
                df = df.top_k(options.limit, by=options.sort_key)

        return df

    @property
    def default_branch(self):
        if self.options.branch is None:
            branches = {b.name for b in self.repo.branches}
            for n in ["main", "master"]:
                if n in branches:
                    self.options.branch = n
                    break
        return self.options.branch

    @property
    def is_large(self):
        return self.commit_count > LARGE_THRESHOLD

    def analyze(self):
        """Perform initial analysis"""
        if self.is_large:
            logger.warning(
                "Large repo with {self.commit_count} revisions, analysis will take a while"
            )

    def _output(
        self,
        output_df: DataFrame,
        options: AnyCmdOptions,
        plot_df: DataFrame | None = None,
        plot_type: SupportedPlotType | None = None,
        **kwargs,
    ):
        output_options = OutputOptions()
        for k, v in options.model_dump().items():
            if hasattr(output_options, k):
                setattr(output_options, k, v)

        if output_options.stdout:
            print(output_df)

        name = kwargs.get("filename", f"{self.name}-report-{time.time()}")

        if output_options.JSON:
            json_file = f"{name}.json"
            output_df.write_json(json_file)
            logger.info(f"File written to {json_file}")
        if output_options.csv:
            csv_file = f"{name}.csv"
            output_df.write_csv(csv_file)
            logger.info(f"File written to {csv_file}")

        if output_options.visualize and plot_type is not None:
            plot_df = plot_df if plot_df is not None else output_df
            plotter = Plotter(plot_df, output_options, plot_type, **kwargs)
            plotter.plot()

    def summary(self, options: SummaryCmdOptions) -> DataFrame:
        """A simple summary with counts of files, contributors, commits."""
        df = self.filtered_revs(options)
        summary_df = DataFrame(
            {
                "name": df["repository"].unique(),
                "files": df["filename"].unique().count(),
                "contributors": df[options.group_by_key].unique().count(),
                "commits": df["sha"].unique().count(),
                "first_commit": df["authored_datetime"].min(),
                "last_commit": df["authored_datetime"].max(),
            }
        )
        self._output(summary_df, options)
        return summary_df

    def revisions(self, options: RevisionsCmdOptions):
        revision_df = self.filtered_revs(options)
        self._output(revision_df, options)
        return revision_df

    def contributor_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        report_df = (
            self.filtered_revs(options)
            .group_by(options.group_by_key)
            .agg(pl.sum("lines"), pl.sum("insertions"), pl.sum("deletions"))
            .with_columns((pl.col("insertions") - pl.col("deletions")).alias("net"))
        )
        self._output(report_df, options)
        return report_df

    def file_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        report_df = (
            self.filtered_revs(options)
            .group_by("filename")
            .agg(pl.sum("lines"), pl.sum("insertions"), pl.sum("deletions"))
            .with_columns((pl.col("insertions") - pl.col("deletions")).alias("net"))
        )
        if (
            isinstance(options.sort_key, str)
            and options.sort_key not in report_df.columns
        ):
            logger.warning("Invalid sort key for this report, using `filename`...")
            options.sort_by = "filename"
        self._output(report_df, options)
        return report_df

    def _blame_with_dt(
        self, rev: str, dt: datetime, options: BlameCmdOptions, **kwargs
    ) -> DataFrame:
        df = self.blame(options, rev, **kwargs)
        return df.with_columns(datetime=dt)

    def blame(
        self,
        options: BlameCmdOptions,
        rev: str | None = None,
        data_field="lines",
        headless=False,
    ) -> DataFrame:
        """For a given revision, lists the number of total lines contributed by the aggregating entity"""

        rev = self.repo.head.commit.hexsha if rev is None else rev
        files_at_rev = self._file_names_at_rev(rev)
        logger.debug(f"Starting blame for rev: {rev}")
        # git blame for each file.
        # so the number of lines items for each file is the number of lines in the
        # file at the specified revision
        # BlameEntry
        blame_map: dict[str, Iterator[BlameEntry]] = {
            f: self.repo.blame_incremental(
                rev,
                f,
                w=self.options.ignore_whitespace,
                no_merges=self.options.ignore_merges,
            )
            for f in files_at_rev.filter(
                options.glob_filter_expr(
                    files_at_rev,
                )
            )
        }
        data: list[dict[str, Any]] = []
        for f, blame_entries in blame_map.items():
            for blame_entry in blame_entries:
                commit: Commit_ish = blame_entry.commit
                author: Actor = commit.author
                committer: Actor = commit.committer
                data.append(
                    {
                        "point_in_time": rev,
                        "filename": f,
                        "sha": commit.hexsha,
                        "line_range": blame_entry.linenos,
                        "author_name": author.name,
                        "author_email": author.email.lower() if author.email else "",
                        "committer_name": committer.name,
                        "committer_email": committer.email.lower()
                        if committer.email
                        else "",
                        "committed_datetime": commit.committed_datetime,
                        "authored_datetime": commit.authored_datetime,
                    }
                )

        blame_df = (
            DataFrame(data)
            .with_columns(pl.col(options.group_by_key).replace(options.aliases))
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
            .with_columns(pl.col("line_range").list.len().alias(data_field))
        )

        agg_df = blame_df.group_by(options.group_by_key).agg(pl.sum(data_field))

        if not options.limit or options.limit <= 0:
            agg_df = agg_df.sort(
                by=options.sort_key, descending=options.sort_descending
            )
        elif options.sort_descending:
            agg_df = agg_df.bottom_k(options.limit, by=options.sort_key)
        else:
            agg_df = agg_df.top_k(options.limit, by=options.sort_key)
        if not headless:
            self._output(
                agg_df,
                options,
                plot_type="blame",
                title=f"{self.name} Blame at {rev[:10] if rev else 'HEAD'}",
                x=f"{data_field}:Q",
                y=options.group_by_key,
                filename=f"{self.name}_blame_by_{options.group_by_key}",
            )

        return agg_df

    def cumulative_blame(
        self, options: BlameCmdOptions, batch_size=2, data_field="lines"
    ) -> DataFrame:
        """For each revision over time, the number of total lines authored or commmitted by
        an actor at that point in time.
        """
        total = DataFrame()
        sha_dates = (
            self.filtered_revs(options, ignore_limit=True)
            .sort(cs.temporal())
            .select(pl.col(("sha", "committed_datetime")))
            .unique("sha", keep="first", maintain_order=True)
            .iter_rows()
        )

        total = DataFrame()

        msg = f"Using {max_cpu_count} cpus"
        logger.info(msg)
        # Manually set up the pool rather than use a context manager, because
        # killing the subprocesses breaks coverage
        with Pool(processes=max_cpu_count, initargs={"daemon": True}) as p:
            fn = functools.partial(self._blame_with_dt, options=options, headless=True)
            blame_frame_results = p.starmap(fn, sha_dates, chunksize=batch_size)

        for blame_dfs in blame_frame_results:
            _ = total.vstack(blame_dfs, in_place=True)

        pivot_df = (
            total.pivot(
                options.group_by_key,
                index="datetime",
                values=data_field,
                aggregate_function="sum",
            )
            .sort(cs.temporal())
            .fill_null(0)
        )
        self._output(
            pivot_df,
            options,
            plot_df=total,
            plot_type="cumulative_blame",
            x="datetime:T",
            y=f"sum({data_field}):Q",
            color=f"{options.group_by_key}:N",
            title=f"{self.name} Cumulative Blame",
            filename=f"{self.name}_cumulative_blame_by_{options.group_by_key}",
        )
        return total

    def bus_factor(self, options: BusFactorCmdOptions) -> DataFrame:
        if options.limit:
            logger.warning(
                "Limit suggested for comprehensive analysis that requires all commits not explicitly excluded (generated files or glob), will ignore limit"
            )
        df = self.filtered_revs(options, ignore_limit=True)
        return df

    def punchcard(self, options: PunchcardCmdOptions) -> DataFrame:
        df = (
            self.filtered_revs(options)
            .filter(pl.col(options.group_by_key) == options.identifier)
            .pivot(
                options.group_by_key,
                values=["lines"],
                index=options.punchcard_key,
                aggregate_function="sum",
            )
            .sort(by=cs.temporal())
        )
        plot_df = df.rename(
            {options.identifier: "count", options.punchcard_key: "time"}
        )
        self._output(
            df,
            options,
            plot_df=plot_df,
            plot_type="punchcard",
            x="hours(time):O",
            y="day(time):O",
            color="sum(count):Q",
            size="sum(count):Q",
            title=f"{options.identifier} Punchcard".title(),
            filename=f"{self.name}_punchcard_{quote(options.identifier)}",
        )
        return df

    def file_timeline(self, options: ActivityReportCmdOptions):
        pass
