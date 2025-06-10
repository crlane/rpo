import fnmatch
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import polars as pl
from git import Commit as GitCommit
from pydantic import BaseModel, Field

from .types import AggregateBy, IdentifyBy, SortBy


class DataSelectionOptions(BaseModel):
    aggregate_by: AggregateBy = Field(
        description="When grouping for reports, this value controls how to group aggregations",
        default="author",
    )
    identify_by: IdentifyBy = Field(
        description="How to identify the actor responsible for commits",
        default="name",
    )
    sort_by: SortBy = Field(
        description="The field to sort on in the resulting DataFrame",
        default="actor",
    )

    @property
    def group_by_key(self):
        return f"{self.aggregate_by}_{self.identify_by}"

    @property
    def sort_key(self):
        return self.group_by_key if self.sort_by == "actor" else self.sort_by


class FileSelectionOptions(BaseModel):
    include_globs: list[str] | None = None
    exclude_globs: list[str] | None = None

    def _glob_filter(
        self, filenames: Iterator[str], globs: str | list[str], include: bool = True
    ):
        if isinstance(globs, str):
            globs = [globs]

        def _filter_func_include(filename: str):
            return any(fnmatch.fnmatch(filename, p) for p in globs)

        def _filter_func_exclude(filename: str):
            return not any(fnmatch.fnmatch(filename, p) for p in globs)

        _filter_func = _filter_func_include if include else _filter_func_exclude
        return filter(_filter_func, filenames)

    def filter_expr(self, filenames: Iterator[str]) -> pl.Expr | bool:
        if self.exclude_globs:
            filter_expr = pl.col("filename").is_in(
                set(self._glob_filter(filenames, self.exclude_globs, include=False))
            )
        elif self.include_globs:
            filter_expr = pl.col("filename").is_in(
                set(self._glob_filter(filenames, self.include_globs, include=True))
            )
        else:
            filter_expr = True

        print(filter_expr)
        return filter_expr


class SummaryCmdOptions(DataSelectionOptions):
    """Options for the ProjectAnalyzer.summary command"""


class ActivityReportCmdOptions(DataSelectionOptions, FileSelectionOptions):
    """Options for the ProjectAnalyzer.activity_report"""


class BlameCmdOptions(DataSelectionOptions, FileSelectionOptions):
    """Options for ProjectAnalyzer.blame and ProjectAnalyzer.cumulative_blame"""


class GitOptions(BaseModel):
    repository: str | Path | PathLike[str] | None = None
    branch: str | None = None


def recursive_getattr(
    obj: object, field: str, separator: str = ".", should_call: bool = True
) -> Any:
    if not field:
        return obj
    try:
        o = getattr(obj, field)
        if callable(o) and should_call:
            return o()
        else:
            return o
    except AttributeError:
        head, _, tail = field.partition(separator)
        return recursive_getattr(getattr(obj, head), tail)


class Commit(BaseModel):
    repository: str
    sha: str
    authored_datetime: datetime
    author_name: str
    author_email: str | None
    committed_datetime: datetime
    committer_name: str
    committer_email: str | None
    summary: str
    # file change info
    filename: str | None = None
    insertions: float | None = None
    deletions: float | None = None
    lines: float | None = None
    change_type: Literal["M", "A", "D"] | None = None

    @classmethod
    def from_git(cls, git_commit: GitCommit, for_repo: str, by_file: bool = False):
        fields = {
            "hexsha": "sha",
            "authored_datetime": "authored_datetime",
            "author.name": "author_name",
            "author.email": "author_email",
            "committed_datetime": "committed_datetime",
            "committer.name": "committer_name",
            "committer.email": "committer_email",
            "summary": "summary",
        }
        base = {v: recursive_getattr(git_commit, f) for f, v in fields.items()}
        base["repository"] = for_repo
        if by_file:
            data = deepcopy(base)
            for f, changes in git_commit.stats.files.items():
                data["filename"] = f
                data.update(**changes)
                yield cls(**data)
