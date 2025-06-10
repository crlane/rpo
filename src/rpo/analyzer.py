import functools
from collections.abc import Iterator
from os import PathLike
from pathlib import Path
from typing import Any

import polars as pl
from git.repo import Repo
from git.repo.base import BlameEntry

from .models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    Commit,
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

    DEFAULT_IGNORE_GLOBS = [
        "*.lock",  # ruby, rust, abunch of things
        "package-lock.json",
        "go.sum",
    ]

    def __init__(
        self,
        repo: Repo | None = None,
        path: str | Path | None = None,
        branch: str | None = None,
        ignore_generated_files: bool | list[str] = False,
        ignore_merges: bool = False,
    ):
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

        if self.repo.bare or self.repo.is_dirty():
            raise ValueError(
                "Repository is either empty has uncommitted changes! Please check the path and/or unstage any changes"
            )
        self.ignore_generated_files = ignore_generated_files
        self.ignore_merges = ignore_merges

        self._revs = None
        self._authors = None
        self._committers = None
        self._branch = branch

    @functools.cache
    def _file_names_at_rev(self, rev: str) -> set[str]:
        raw = self.repo.git.ls_tree("-r", "--name-only", rev)
        return set(raw.strip().split("\n"))

    @property
    def revs(self):
        """The git revisions property."""
        if self._revs is None:
            revs: list[Commit] = []
            for c in self.repo.iter_commits(no_merges=self.ignore_merges):
                revs.extend(Commit.from_git(c, self.path.name, by_file=True))
            self._revs = pl.DataFrame(revs)
        return self._revs

    @property
    def default_branch(self):
        if self._branch is None:
            branches = {b.name for b in self.repo.branches}
            for n in ["main", "master"]:
                if n in branches:
                    self._branch = n
                    break
        return self._branch

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

    def contributor_report(
        self, options: ActivityReportCmdOptions | None = None
    ) -> pl.DataFrame:
        if options is None:
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
            self.revs.filter(options.filter_expr(iter(self.revs["filename"])))
            .group_by(options.group_by_key)
            .agg(pl.sum("insertions"), pl.sum("deletions"), pl.sum("lines"))
            .sort(by=options.sort_key)
        )

    def file_report(
        self, options: ActivityReportCmdOptions | None = None
    ) -> pl.DataFrame:
        if options is None:
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
            self.revs.filter(options.filter_expr(iter(self.revs["filename"])))
            .group_by("filename", options.group_by_key)
            .agg(pl.sum("insertions"), pl.sum("deletions"), pl.sum("lines"))
            .sort(by=options.sort_key)
        )

    def blame(
        self,
        options: BlameCmdOptions | None = None,
        rev: str | None = None,
        ignore_whitespace: bool = False,
        ignore_merges: bool = False,
    ) -> pl.DataFrame:
        """For a given revision, lists the number of total lines contributed by the aggregating entity"""
        rev = self.repo.head.commit.hexsha if rev is None else rev
        files_at_rev = self._file_names_at_rev(rev)

        if options is None:
            options = BlameCmdOptions()

        if options.include_globs:
            files_at_rev = filename_glob_filter(
                iter(files_at_rev), options.include_globs
            )
        elif options.exclude_globs:
            files_at_rev = filename_glob_filter(
                iter(files_at_rev), options.exclude_globs, include=False
            )
        rev_opts: list[str] = []
        if ignore_whitespace:
            rev_opts.append("-w")
        if ignore_merges:
            rev_opts.append("--no-merges")
        # git blame for each file.
        # so the number of lines items for each file is the number of lines in the
        # file at the specified revision
        # BlameEntry
        blame_map: dict[str, Iterator[BlameEntry]] = {
            f: self.repo.blame_incremental(rev, f, rev_opts=rev_opts)
            for f in files_at_rev
        }
        data: list[dict[str, Any]] = []
        for f, blame_entries in blame_map.items():
            for blame_entry in blame_entries:
                data.append(
                    {
                        "point_in_time": rev,
                        "filename": f,
                        "sha": blame_entry.commit.hexsha,
                        "line_range": blame_entry.linenos,
                        "author_name": blame_entry.commit.author.name,
                        "author_email": blame_entry.commit.author.email,
                        "committer_name": blame_entry.commit.committer.name,
                        "committer_email": blame_entry.commit.committer.email,
                        "committed_datetime": blame_entry.commit.committed_datetime,
                        "authored_datetime": blame_entry.commit.authored_datetime,
                    }
                )

        lc_alias = "line_count"

        blame_df = pl.DataFrame(data).with_columns(
            pl.col("line_range").list.len().alias(lc_alias)
        )
        return (
            blame_df.group_by(options.group_by_key)
            .agg(pl.sum(lc_alias))
            .sort(by=options.sort_key)
        )

    def cumulative_blame(self, options: BlameCmdOptions | None = None) -> pl.DataFrame:
        """For each revision over time, the number of total lines authored or commmitted by
        an actor at that point in time.
        """
        if not options:
            options = BlameCmdOptions()
        raise NotImplementedError()

    def bus_factor(self) -> pl.DataFrame:
        raise NotImplementedError()

    def punchcard(self) -> pl.DataFrame:
        raise NotImplementedError()
