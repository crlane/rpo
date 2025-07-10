import functools
import itertools
import logging
import time
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count
from pathlib import Path
from urllib.parse import quote

import polars as pl
import polars.selectors as cs
from dateutil.parser import parse as dateparse
from git.repo import Repo
from polars import DataFrame

from rpo.git_parser import GitParser

from .db import DB
from .models import (
    ActivityReportCmdOptions,
    BatchCheckRecord,
    BlameCmdOptions,
    BusFactorCmdOptions,
    DataSelectionOptions,
    FileSaveOptions,
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
        self._objects = None

        self.name = self.options.path.name
        self._db = DB(name=self.name, in_memory=in_memory, initialize=True)

    @property
    def objects(self) -> DataFrame:
        if self._objects is None:
            p = self.repo.git.rev_list(
                "--all", "--objects", "--no-merges", as_process=True
            )
            result = self.repo.git.cat_file(
                "--batch-check=\"%(objectname) %(objecttype) '%(rest)' %(deltabase)\"",
                istream=p.stdout.name,
            )
            df = DataFrame(
                BatchCheckRecord.from_raw(a.strip('"')) for a in result.split("\n")
            )
            self._objects = df

            self._db.insert_objects(df)
        return self._objects

    def _file_names_at_rev(self, rev: str, options: DataSelectionOptions) -> DataFrame:
        raw = self.repo.git.ls_tree("-r", "--format=%(objectname) %(path)", rev)
        vals = [
            dict(zip(("blob_id", "path"), a.split(maxsplit=1)))
            for a in raw.strip().split("\n")
        ]
        # TODO: make sure this uses filter. Also, how can we
        # Make sure anything that needs to filter filters
        df = DataFrame(vals)
        return df.filter(options.glob_filter_expr(df["path"]))

    @property
    def commit_count(self):
        if self._commit_count is None:
            self._commit_count = self.repo.head.commit.count()
        return self._commit_count

    @property
    def revs(self):
        """The git revisions property."""
        if self._revs is None:
            _, sha = self._db.get_latest_change_tuple()
            rev_spec = (
                self.repo.head.commit.hexsha
                if sha is None
                else f"{sha}...{self.repo.head.commit.hexsha}"
            )

            # git rev-list --all --format="%H,%cN,%cE,%cI,%aN,%aE,%aI,%T"
            # git log --format=%H,%aN,%aE,%aI,%cN,%cE,%cI --find-renames --numstat
            GITLOG_FORMAT = "%H|'%cN'|%cE|%cI|'%aN'|%aE|%aI|%T"
            result = self.repo.git.log(
                rev_spec,
                numstat=True,
                find_renames=True,
                no_merges=self.options.ignore_merges,
                w=self.options.ignore_whitespace,
                format=GITLOG_FORMAT,
            ).split("\n")

            self._revs = DataFrame()
            base: dict[str, str | int | datetime] = {}
            keys = (
                "sha",
                "committer_name",
                "committer_email",
                "committed_datetime",
                "author_name",
                "author_email",
                "authored_datetime",
                "tree_oid",
            )
            for line in result:
                if not line:
                    continue
                vals = [w.strip("'") for w in line.split("|")]
                if len(keys) == len(vals):  # file list
                    prev = base
                    base = {}
                    for i, k in enumerate(keys):
                        if k.endswith("datetime"):
                            dt = dateparse(vals[i])
                            try:
                                assert dt.utcoffset() is not None
                            except (ValueError, AssertionError):
                                # sometimes, there are weird offsets, default to UTC
                                dt = dt.replace(tzinfo=timezone.utc)
                                # some of the offsets don't work
                            base[k] = dt
                        else:
                            base[k] = vals[i]

                    if prev:
                        try:
                            _ = self._revs.vstack(DataFrame(prev), in_place=True)
                        except pl.ShapeError:
                            logger.debug(
                                f"Found two commit header lines in a row, likely a merge commit: {prev['sha']}"
                            )
                        except Exception as e:
                            logger.exception(f"Unknown error occurred: {e}")
                else:
                    insertions, deletions, path = line.split("\t")
                    base["path"] = path
                    base["insertions"] = int(insertions) if insertions.isdigit() else 0
                    base["deletions"] = int(deletions) if deletions.isdigit() else 0
                    base["lines"] = base["insertions"] + base["deletions"]
                    base["is_binary"] = base["lines"] == 0

            _ = self._revs.vstack(DataFrame(base), in_place=True).rechunk()
            assert self._revs is not None and not self._revs.is_empty()
            self._db.insert_file_changes(self._revs)
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
        df = self.revs.with_columns(
            pl.col(options.group_by_key).replace(options.aliases)
        ).filter(pl.col(options.group_by_key).is_in(options.exclude_users).not_())
        df = df.filter(
            options.glob_filter_expr(
                df["path"],
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

    def analyze(self, options: FileSaveOptions):
        """Perform initial analysis"""
        if self.is_large:
            logger.warning(
                "Large repo with {self.commit_count} revisions, analysis will take a while"
            )
        df = self.objects.sort(by="path")
        self._output(df, options)
        return df

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
                "files": df["path"].unique().count(),
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
        # lines changed
        report_df = (
            self.filtered_revs(options)
            .group_by(options.group_by_key)
            .agg(pl.sum("lines"), pl.sum("insertions"), pl.sum("deletions"))
            .with_columns((pl.col("insertions") - pl.col("deletions")).alias("net"))
        ).sort(by="lines")

        # commits created
        # self.filtered_revs(options).group_by(options.group_by_key).agg(pl.len().alias('commit_count')).sort(by='commit_count').sum()
        self._output(report_df, options)
        return report_df

    def file_report(self, options: ActivityReportCmdOptions) -> DataFrame:
        # changes per file
        report_df = (
            self.filtered_revs(options)
            .group_by("path")
            .agg(pl.sum("lines"), pl.sum("insertions"), pl.sum("deletions"))
            .with_columns((pl.col("insertions") - pl.col("deletions")).alias("net"))
        )
        if (
            isinstance(options.sort_key, str)
            and options.sort_key not in report_df.columns
        ):
            logger.warning("Invalid sort key for this report, using `path`...")
            options.sort_by = "path"

        # commits per file
        # self.filtered_revs(options).group_by('path').agg(pl.len().alias('commits')).sort(by='commits')
        self._output(report_df, options)
        return report_df

    def blame(
        self,
        options: BlameCmdOptions,
        rev: str | None = None,
        data_field="num_lines",
        headless=False,
    ) -> DataFrame:
        """For a given revision, lists the number of total lines contributed by the aggregating entity

        To check this, you can use the git command to show the number of commits

        ```
        git blame --line-porcelain file |
           sed -n 's/^author //p' |
           sort | uniq -c | sort -rn
        ```
        """

        rev = self.repo.head.commit.hexsha if rev is None else rev
        files_at_rev = self._file_names_at_rev(rev, options)
        logger.debug(f"Starting blame for rev: {rev}")

        gp = GitParser()
        inc_blame_result = itertools.chain.from_iterable(
            itertools.chain.from_iterable(
                gp.parse_blame_result(r, f[0], f[1])
                for r in self.repo.git.blame(rev, "--incremental", "--", f[1]).split(
                    "\n"
                )
            )
            for f in files_at_rev.iter_rows()
        )

        blame_df = DataFrame((dict(at_rev=rev, **d) for d in inc_blame_result))

        revs_df = self.filtered_revs(options)
        joined_df = pl.sql(
            "SELECT * from blame_df bdf JOIN revs_df rdf on bdf.commit_sha = rdf.sha"
        ).collect()
        # git blame for each file.

        # NOTE: this is being used in a cumulative fashion, return before aggregating
        if headless:
            return joined_df

        # this turns into blame output, before is raw balme that j
        agg_df = joined_df.pivot(
            on=["at_rev"],
            index=[options.group_by_key],
            values=[data_field],
            aggregate_function="sum",
        ).rename({rev: data_field})

        if not options.limit or options.limit <= 0:
            agg_df = agg_df.sort(
                by=options.sort_key, descending=options.sort_descending
            )
        elif options.sort_descending:
            agg_df = agg_df.bottom_k(options.limit, by=options.sort_key)
        else:
            agg_df = agg_df.top_k(options.limit, by=options.sort_key)

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
        self, options: BlameCmdOptions, batch_size=2, data_field="num_lines"
    ) -> DataFrame:
        """For each revision over time, the number of total lines authored or commmitted by
        an actor at that point in time.
        """
        total = DataFrame()
        shas = (
            self.filtered_revs(options, ignore_limit=True)
            .sort(cs.temporal())
            .select(pl.col("sha"))
            .unique()
            .iter_rows()
        )
        total = DataFrame()

        msg = f"Using {max_cpu_count} cpus"
        logger.info(msg)
        # Manually set up the pool rather than use a context manager, because
        # killing the subprocesses breaks coverage
        with Pool(processes=max_cpu_count, initargs={"daemon": True}) as p:
            fn = functools.partial(self.blame, options, headless=True)
            blame_frame_results = p.starmap(fn, shas, chunksize=batch_size)

        for blame_dfs in blame_frame_results:
            _ = total.vstack(blame_dfs, in_place=True)

        pivot_df = (
            total.pivot(
                on=[options.dt_field],
                index=options.group_by_key,
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
