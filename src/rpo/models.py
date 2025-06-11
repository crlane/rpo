from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

import polars as pl
from git import Commit as GitCommit
from pydantic import BaseModel, Field

from .types import AggregateBy, IdentifyBy, SortBy


class OutputOptions(BaseModel):
    formats: Iterable[Path | str] = Field(
        description="Path where the data should be saved.", default=()
    )


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
    sort_descending: bool = Field(
        description="If true, sorts from largest to smallest", default=False
    )
    limit: int = Field(
        description="Maximum number of records to return. Applied after sort",
        default=1_000,
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

    def _generated_file_globs(self) -> Iterable[str]:
        return [
            "*.lock",  # ruby, rust, abunch of things
            "package-lock.json",
            "go.sum",
        ]

    def glob_filter_expr(
        self, filenames: pl.Series | Iterable[str], exclude_generated: bool = False
    ) -> list[bool]:
        if self.exclude_globs:
            filter_expr = list(
                not any(fnmatch(filename, p) for p in self.exclude_globs)
                for filename in filenames
            )
        elif self.include_globs:
            filter_expr = list(
                any(fnmatch(filename, p) for p in self.include_globs)
                for filename in filenames
            )
        elif exclude_generated:
            filter_expr = list(
                not any(fnmatch(filename, p) for p in self._generated_file_globs())
                for filename in filenames
            )
        else:
            filter_expr = list(True for _ in filenames)

        return filter_expr


class SummaryCmdOptions(DataSelectionOptions, OutputOptions):
    """Options for the ProjectAnalyzer.summary command"""


class ActivityReportCmdOptions(
    DataSelectionOptions, FileSelectionOptions, OutputOptions
):
    """Options for the ProjectAnalyzer.activity_report"""


class BlameCmdOptions(DataSelectionOptions, FileSelectionOptions, OutputOptions):
    """Options for ProjectAnalyzer.blame and ProjectAnalyzer.cumulative_blame"""


class GitOptions(BaseModel):
    branch: str | None = None
    allow_dirty: bool = False
    ignore_merges: bool = False
    ignore_whitespace: bool = False
    ignore_generated_files: bool = False


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
