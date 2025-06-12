import functools
import itertools
from collections.abc import Iterable, Iterator
from datetime import datetime
from os import PathLike, process_cpu_count
from pathlib import Path
from typing import Any

import polars as pl
import polars.selectors as cs
from git.repo import Repo
from git.repo.base import BlameEntry
from joblib import Parallel, delayed

from .models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    Commit,
    DataSelectionOptions,
    GitOptions,
    SummaryCmdOptions,
)


class ProjectAnalyzer:
    def __init__(self, project: PathLike[str]):
        pass


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
        allow_dirty: bool = False,
    ):
        self.options = options if options else GitOptions()
        if path:
            if isinstance(path, str):
                path = Path(path)
            self.path = path
            self.repo = Repo(path)
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

        self._revs = None

    @functools.cache
    def _file_names_at_rev(self, rev: str) -> pl.Series:
        raw = self.repo.git.ls_tree("-r", "--name-only", rev)
        vals = raw.strip().split("\n")
        return pl.Series(name="filename", values=vals)

    @property
    def revs(self):
        """The git revisions property."""
        if self._revs is None:
            revs: list[Commit] = []
            for c in self.repo.iter_commits(no_merges=self.options.ignore_merges):
                revs.extend(Commit.from_git(c, self.path.name, by_file=True))
            self._revs = pl.DataFrame(revs)
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

    def summary(self, options: SummaryCmdOptions | None = None) -> pl.DataFrame:
        """A simple summary with counts of files, contributors, commits."""
        if not options:
            options = SummaryCmdOptions()

        return pl.DataFrame(
            {
                "name": self.revs["repository"].unique(),
                "files": self.revs["filename"].unique().count(),
                "contributors": self.revs[options.group_by_key].unique().count(),
                "commits": self.revs["sha"].unique().count(),
                "first_commit": self.revs["authored_datetime"].min(),
                "last_commit": self.revs["authored_datetime"].max(),
            }
        )

    def revisions(self, options: DataSelectionOptions):
        return self.revs.sort(options.sort_key).limit(options.limit)

    def contributor_report(
        self, options: ActivityReportCmdOptions | None = None
    ) -> pl.DataFrame:
        if not options:
            options = ActivityReportCmdOptions()

        if options.aggregate_by.lower() not in [
            "author",
            "committer",
        ] or options.identify_by not in [
            "name",
            "email",
        ]:
            msg = """Must aggregate by exactly one of `author` or `committer`,\\
                    and identify by either `name` or `email`. All other values are errors!
            """
            raise ValueError(msg)

        return (
            self.revs.filter(
                options.glob_filter_expr(
                    self.revs["filename"],
                )
            )
            .group_by(options.group_by_key)
            .agg(pl.sum("insertions"), pl.sum("deletions"), pl.sum("lines"))
            .sort(by=options.sort_key)
        )

    def file_report(
        self, options: ActivityReportCmdOptions | None = None
    ) -> pl.DataFrame:
        if not options:
            options = ActivityReportCmdOptions()
        if options.aggregate_by not in [
            "author",
            "committer",
        ] or options.identify_by not in [
            "name",
            "email",
        ]:
            msg = """Must aggregate by exactly one of `author` or `committer`,\\
                    and identify by either `name` or `email`. All other values are errors!
            """
            raise ValueError(msg)

        return (
            self.revs.filter(
                options.glob_filter_expr(
                    self.revs["filename"],
                )
            )
            .group_by("filename", options.group_by_key)
            .agg(pl.sum("insertions"), pl.sum("deletions"), pl.sum("lines"))
            .sort(by=options.sort_key)
        )

    def blame(
        self,
        options: BlameCmdOptions | None = None,
        rev: str | None = None,
        k: int | None = None,
    ) -> pl.DataFrame:
        """For a given revision, lists the number of total lines contributed by the aggregating entity"""
        rev = self.repo.head.commit.hexsha if rev is None else rev
        files_at_rev = self._file_names_at_rev(rev)

        if not options:
            options = BlameCmdOptions()

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
                data.append(
                    {
                        "point_in_time": rev,
                        "filename": f,
                        "sha": blame_entry.commit.hexsha,  # noqa
                        "line_range": blame_entry.linenos,
                        "author_name": blame_entry.commit.author.name,  # noqa
                        "author_email": blame_entry.commit.author.email.lower(),  # noqa
                        "committer_name": blame_entry.commit.committer.name,  # noqa
                        "committer_email": blame_entry.commit.committer.email.lower(),  # noqa
                        "committed_datetime": blame_entry.commit.committed_datetime,  # noqa
                        "authored_datetime": blame_entry.commit.authored_datetime,  # noqa
                    }
                )

        lc_alias = "line_count"

        blame_df = pl.DataFrame(data).with_columns(
            pl.col("line_range").list.len().alias(lc_alias)
        )
        return (
            blame_df.group_by(options.group_by_key)
            .agg(pl.sum(lc_alias))
            .top_k(k or 3, by=lc_alias)
            .sort(by=options.sort_key, descending=options.sort_descending)
        )

    def cumulative_blame(self, options: BlameCmdOptions | None = None) -> pl.DataFrame:
        """For each revision over time, the number of total lines authored or commmitted by
        an actor at that point in time.
        """
        if not options:
            options = BlameCmdOptions()
        total = pl.DataFrame()
        rev_batches = itertools.batched(
            self.revs.sort(cs.temporal())
            .select(pl.col("sha"), pl.col("committed_datetime"))
            .unique()
            .iter_rows(),
            n=25,
        )

        def _get_blame_for_batches(
            rev_batch: Iterable[tuple[str, datetime]],
        ) -> Iterable[pl.DataFrame]:
            results = pl.DataFrame()
            for rev_sha, dt in itertools.chain(rev_batch):
                blame_df = self.blame(options, rev_sha)
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

        return total

    def bus_factor(self) -> pl.DataFrame:
        raise NotImplementedError()

    def punchcard(self) -> pl.DataFrame:
        raise NotImplementedError()

    def output(self, data: pl.DataFrame, output_paths: Iterable[Path | str]):
        if not output_paths:
            print(data)
            return

        for fp in output_paths:
            if isinstance(fp, str):
                fp = Path(fp)
            if fp.name.endswith(".csv"):
                data.write_csv(fp)
            elif fp.name.endswith(".json"):
                data.write_json(fp)
