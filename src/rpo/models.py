from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from fnmatch import fnmatch
from os import PathLike
from typing import Any, Literal

import polars as pl
import polars.selectors as cs
from git import Commit as GitCommit
from pydantic import BaseModel, Field

from .types import AggregateBy, IdentifyBy, SortBy


class FileSaveOptions(BaseModel):
    output_file_paths: list[PathLike[str]] | None = Field(
        description="Path where the data should be saved.", default=None
    )


class PlotOptions(BaseModel):
    img_location: PathLike[str] | None = Field(
        description="Where to save the file", default=None
    )


class OutputOptions(PlotOptions, FileSaveOptions):
    pass


class DataSelectionOptions(BaseModel):
    aggregate_by: AggregateBy = Field(
        description="When grouping for reports, this value controls how to group aggregations",
        default="author",
    )
    identify_by: IdentifyBy = Field(
        description="How to identify the user responsible for commits",
        default="name",
    )
    sort_by: SortBy = Field(
        description="The field to sort on in the resulting DataFrame",
        default="user",
    )
    sort_descending: bool = Field(
        description="If true, sorts from largest to smallest", default=False
    )
    limit: int = Field(
        description="Maximum number of files to return. Applied after sort",
        default=0,
        ge=0,
    )
    aliases: dict[str, str] = Field(
        description="A dictionary matching an alias to the value it should be replaced with before analysis. Useful for correcting misspellings, changed email addresses, etc. in the git history without alterning the repository history.",
        default={},
    )
    exclude_users: list[str] = Field(
        description="A list of user identifiers (name or email) to exclude from analyis. Useful for ignore commits by bots.",
        default=[],
    )
    include_globs: list[str] | None = None
    exclude_globs: list[str] | None = None
    exclude_generated: bool = False

    @property
    def group_by_key(self):
        return f"{self.aggregate_by}_{self.identify_by}"

    @property
    def sort_key(self):
        if self.sort_by == "user":
            return self.group_by_key
        elif self.sort_by == "numeric":
            return cs.numeric()
        elif self.sort_by == "temporal":
            return cs.temporal()
        elif self.sort_by == "first":
            return cs.first()
        elif self.sort_by == "last":
            return cs.last()
        else:
            return pl.col(self.sort_by.lower())

    def _generated_file_globs(self) -> Iterable[str]:
        return [
            "*.lock",  # ruby, rust, abunch of things
            "package-lock.json",
            "go.sum",
            "node_modules/*",
        ]

    def glob_filter_expr(self, filenames: pl.Series | Iterable[str]):
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
        elif self.exclude_generated:
            filter_expr = list(
                not any(fnmatch(filename, p) for p in self._generated_file_globs())
                for filename in filenames
            )
        else:
            filter_expr = list(True for _ in filenames)

        return filter_expr


class RevisionsCmdOptions(DataSelectionOptions, FileSaveOptions):
    """Options for the ProjectAnalyzer.revisions command"""


class SummaryCmdOptions(DataSelectionOptions, FileSaveOptions):
    """Options for the ProjectAnalyzer.summary command"""


class ActivityReportCmdOptions(DataSelectionOptions, OutputOptions):
    """Options for the ProjectAnalyzer.activity_report"""


class BlameCmdOptions(DataSelectionOptions, OutputOptions):
    """Options for ProjectAnalyzer.blame and ProjectAnalyzer.cumulative_blame"""


class BusFactorCmdOptions(DataSelectionOptions, OutputOptions):
    """Options for ProjectAnalyzer.bus_factor"""


class PunchcardCmdOptions(DataSelectionOptions, OutputOptions):
    """Options for ProjectAnalyzer.punchcard"""

    identifier: str

    @property
    def punchcard_key(self):
        if self.aggregate_by == "committer":
            return "committed_datetime"
        return "authored_datetime"


class GitOptions(BaseModel):
    branch: str | None = None
    allow_dirty: bool = False
    ignore_merges: bool = False
    ignore_whitespace: bool = False
    ignore_generated_files: bool = False
    use_gitignore: bool = True


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
            if field.endswith("email"):
                o = str(o).lower()
            return o
    except AttributeError:
        head, _, tail = field.partition(separator)
        return recursive_getattr(getattr(obj, head), tail)


class FileChangeCommitRecord(BaseModel):
    repository: str
    sha: str
    authored_datetime: datetime
    author_name: str
    author_email: str | None
    committed_datetime: datetime
    committer_name: str
    committer_email: str | None

    summary: str
    gpgsig: str | None = None
    # file change info
    filename: str | None = None
    insertions: float | None = None
    deletions: float | None = None
    lines: float | None = None
    change_type: Literal["M", "A", "D"] | None = None
    is_binary: bool | None = None

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
            "gpgsig": "gpgsig",
        }
        base = {v: recursive_getattr(git_commit, f) for f, v in fields.items()}
        base["repository"] = for_repo
        if by_file:
            data = deepcopy(base)
            for f, changes in git_commit.stats.files.items():
                data["filename"] = f
                # if all the line change statistics are 0, it's a binary file
                lines_changed = sum(
                    changes.get(t, 0) for t in ("insertions", "deletions", "lines")
                )
                data["is_binary"] = not lines_changed
                data.update(**changes)
                yield cls(**data)
