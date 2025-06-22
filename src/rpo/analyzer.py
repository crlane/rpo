import functools
import itertools
import logging
from collections.abc import Iterable, Iterator
from datetime import datetime
from os import PathLike, process_cpu_count
from pathlib import Path
from typing import Any
from urllib.parse import quote

import polars as pl
import polars.selectors as cs
from git import Actor
from git.repo import Repo
from git.repo.base import BlameEntry
from git.types import Commit_ish
from joblib import Parallel, delayed
from polars import DataFrame

from rpo.plotting import Plotter
from rpo.types import SupportedPlotType

from .db import DB
from .models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    BusFactorCmdOptions,
    DataSelectionOptions,
    FileChangeCommitRecord,
    GitOptions,
    PunchcardCmdOptions,
    RevisionsCmdOptions,
    SummaryCmdOptions,
)
from .writer import Writer

logger = logging.getLogger(__name__)

LARGE_THRESHOLD = 10_000


def init_db(name: str, persistence: bool, initialize=False):
    db = DB(name=name, in_memory=not persistence)
    if initialize:  # new
        db.create_tables()
    return db


class ProjectAnalyzer:
    def __init__(self, project: PathLike[str]):
        self.path = Path(project)


class RepoAnalyzer:
    """
    `RepoAnalyzer` connects `git.repo.Repo` to polars dataframes
    for on demand analysis.
    """

    def __init__(
        self,
        repo: Repo | None = None,
        path: str | Path | None = None,
        options: GitOptions | None = None,
        persistence: bool = False,
    ):
        self.options = options if options else GitOptions()
        self.persistence = persistence
        if path:
            if isinstance(path, str):
                path = Path(path)
            if (path / ".git").exists():
                self.path = path
                self.repo = Repo(path)
            else:
                raise ValueError("Specified path does not contain '.git' directory")
        elif repo:
            self.repo = repo
            self.path = Path(repo.common_dir).parent
        else:
            raise ValueError("Must specify either a `path` or pass a Repo object")

        if self.repo.bare:
            raise ValueError(
                "Repository has no commits! Please check the path and/or unstage any changes"
            )
        elif self.repo.is_dirty() and not self.options.allow_dirty:
            raise ValueError(
                "Repository has uncommitted changes! Please stash any changes or use `--allow-dirty`."
            )

        self._commit_count = None

        self._revs = None
        self._db = init_db(self.path.name, self.persistence, initialize=True)

    def __getstate__(self) -> object:
        state = self.__dict__.copy()
        # don't pickle _db. Necessary for joblib multiprocessing.
        # if that can be removed, get rid of this.
        del state["_db"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # don't pickle _db. Necessary for joblib multiprocessing.
        # if that can be removed, get rid of this.
        self._db = init_db(self.path.name, self.persistence, initialize=False)

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
        latest: tuple[datetime, str | None] = self._db.get_latest_change_tuple() or (
            datetime.min,
            None,
        )
        _, sha = latest

        if self._revs is None:
            revs: list[FileChangeCommitRecord] = []
            rev_spec = self.repo.head if sha is None else f"{sha}...{self.repo.head}"
            for c in self.repo.iter_commits(
                rev_spec, no_merges=self.options.ignore_merges
            ):
                revs.extend(
                    FileChangeCommitRecord.from_git(c, self.path.name, by_file=True)
                )

            self._revs = self._db.insert_file_changes(revs)
        assert self._revs is not None
        count = self._revs.unique("sha").height

        assert count == self.commit_count == self._db.change_count(), (
            f"Mismatch: {count} != {self.commit_count}"
        )
        return self._revs

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
        options: SummaryCmdOptions
        | BlameCmdOptions
        | PunchcardCmdOptions
        | RevisionsCmdOptions
        | ActivityReportCmdOptions,
        output_df: DataFrame,
        plot_df: DataFrame | None = None,
        plot_type: SupportedPlotType | None = None,
        **kwargs,
    ):
        if locs := options.output_file_paths:
            writer = Writer(locs)
            writer.write(output_df)

        if hasattr(options, "img_location"):
            if img_loc := options.img_location:
                assert plot_type is not None
                plot_df = plot_df if plot_df is not None else output_df
                plotter = Plotter(img_loc, df=plot_df, plot_type=plot_type, **kwargs)
                plotter.plot()

    def _check_agg_and_id_options(
        self,
        options: DataSelectionOptions,
    ):
        if options.aggregate_by.lower() not in [
            "author",
            "committer",
        ] or options.identify_by.lower() not in [
            "name",
            "email",
        ]:
            msg = """Must aggregate by exactly one of `author` or `committer`,\\
                    and identify by either `name` or `email`. All other values are errors!
            """
            raise ValueError(msg)

    def summary(self, options: SummaryCmdOptions) -> DataFrame:
        """A simple summary with counts of files, contributors, commits."""
        df = self.revs.with_columns(
            pl.col(options.group_by_key).replace(options.aliases)
        )
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
        self._output(options, summary_df)
        return summary_df

    def revisions(self, options: RevisionsCmdOptions):
        df = self.revs.with_columns(
            pl.col(options.group_by_key).replace(options.aliases)
        ).filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())

        if not options.limit or options.limit <= 0:
            revision_df = df.sort(by=options.sort_key)
        elif options.sort_descending:
            revision_df = df.bottom_k(options.limit, by=options.sort_key)
        else:
            revision_df = df.top_k(options.limit, by=options.sort_key)
        self._output(options, revision_df)
        return revision_df

    def contributor_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        self._check_agg_and_id_options(options)
        report_df = (
            self.revs.with_columns(
                pl.col(options.group_by_key).replace(options.aliases)
            )
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
            .filter(
                options.glob_filter_expr(
                    self.revs["filename"],
                )
            )
            .group_by(options.group_by_key)
            .agg(pl.sum("lines"), pl.sum("insertions"), pl.sum("deletions"))
            .with_columns((pl.col("insertions") - pl.col("deletions")).alias("net"))
        )

        if not options.limit or options.limit <= 0:
            report_df = report_df.sort(by=options.sort_key)
        elif options.sort_descending:
            report_df = report_df.bottom_k(options.limit, by=options.sort_key)
        else:
            report_df = report_df.top_k(options.limit, by=options.sort_key)
        self._output(options, report_df)
        return report_df

    def file_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        self._check_agg_and_id_options(options)
        report_df = (
            self.revs.with_columns(
                pl.col(options.group_by_key).replace(options.aliases)
            )
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
            .filter(
                options.glob_filter_expr(
                    self.revs["filename"],
                )
            )
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
        if not options.limit or options.limit <= 0:
            report_df = report_df.sort(by=options.sort_key)
        elif options.sort_descending:
            report_df = report_df.bottom_k(options.limit, by=options.sort_key)
        else:
            report_df = report_df.top_k(options.limit, by=options.sort_key)
        self._output(options, report_df)
        return report_df

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

        rev_opts: list[str] = []
        if self.options.ignore_whitespace:
            rev_opts.append("-w")
        if self.options.ignore_merges:
            rev_opts.append("--no-merges")
        # git blame for each file.
        # so the number of lines items for each file is the number of lines in the
        # file at the specified revision
        # BlameEntry
        blame_map: dict[str, Iterator[BlameEntry]] = {
            f: self.repo.blame_incremental(rev, f, rev_opts=rev_opts)
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
                options,
                agg_df,
                plot_type="blame",
                title=f"{self.path.name} Blame at {rev[:10] if rev else 'HEAD'}",
                x=f"{data_field}:Q",
                y=options.group_by_key,
                filename=f"{self.path.name}_blame_by_{options.group_by_key}.png",
            )

        return agg_df

    def cumulative_blame(
        self, options: BlameCmdOptions, batch_size=25, data_field="lines"
    ) -> DataFrame:
        """For each revision over time, the number of total lines authored or commmitted by
        an actor at that point in time.
        """
        total = DataFrame()
        rev_batches = itertools.batched(
            self.revs.with_columns(
                pl.col(options.group_by_key).replace(options.aliases)
            )
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
            .sort(cs.temporal())
            .select(pl.col("sha"), pl.col("committed_datetime"))
            .unique()
            .iter_rows(),
            n=batch_size,
        )

        def _get_blame_for_batches(
            rev_batch: Iterable[tuple[str, datetime]],
        ) -> DataFrame:
            results = DataFrame()
            for rev_sha, dt in itertools.chain(rev_batch):
                blame_df = self.blame(
                    options, rev_sha, data_field=data_field, headless=True
                )
                _ = blame_df.insert_column(
                    blame_df.width,
                    pl.Series(
                        name="datetime", values=itertools.repeat(dt, blame_df.height)
                    ),
                )
                results = results.vstack(blame_df)
            return results

        machine_cpu_count: int = process_cpu_count() or 2
        blame_frames_batched = Parallel(
            n_jobs=max(2, machine_cpu_count), return_as="generator"
        )(delayed(_get_blame_for_batches)(b) for b in rev_batches)

        for blame_dfs in blame_frames_batched:
            total = pl.concat([total, blame_dfs])

        pivot_df = (
            total.pivot(
                [options.group_by_key],
                index="datetime",
                values=data_field,
                aggregate_function="sum",
            )
            .sort(cs.temporal())
            .fill_null(0)
        )
        self._output(
            options,
            pivot_df,
            plot_df=total,
            plot_type="cumulative_blame",
            x="datetime:T",
            y=f"sum({data_field}):Q",
            color=f"{options.group_by_key}:N",
            title=f"{self.path.name} Cumulative Blame",
            filename=f"{self.path.name}_cumulative_blame_by_{options.group_by_key}.png",
        )
        return total

    def bus_factor(self, options: BusFactorCmdOptions) -> DataFrame:
        df = self.revs.with_columns(
            pl.col(options.group_by_key)
            .replace(options.aliases)
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
        )
        return df

    def punchcard(self, options: PunchcardCmdOptions) -> DataFrame:
        self._check_agg_and_id_options(options)
        df = (
            self.revs.with_columns(
                pl.col(options.group_by_key).replace(options.aliases)
            )
            .filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
            .filter(options.glob_filter_expr(self.revs["filename"]))
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
            options,
            df,
            plot_df=plot_df,
            plot_type="punchcard",
            x="hours(time):O",
            y="day(time):O",
            color="sum(count):Q",
            size="sum(count):Q",
            title="{options.identifier} Punchcard".title(),
            filename=f"{self.path.name}_punchcard_{quote(options.identifier)}.png",
        )
        return df

    def file_timeline(self, options: ActivityReportCmdOptions):
        pass
