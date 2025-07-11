from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

import polars as pl
import polars.selectors as cs
from git import Commit as GitCommit
from pydantic import BaseModel, Field


class FileSaveOptions(BaseModel):
    JSON: bool = Field(default=False, description="Save output as json")
    csv: bool = Field(default=False, description="Save output as csv")
    stdout: bool = Field(default=True, description="Print output to stdout")


class PlotOptions(BaseModel):
    visualize: bool = Field(
        description="If true, create a vizualization of the result",
        default=False,
    )
    img_location: Path = Field(
        default=Path.cwd(),
        description="where to save visualization output. Defaults to an 'img' subdirectory in the current working directory",
    )


class OutputOptions(PlotOptions, FileSaveOptions):
    pass


class DataSelectionOptions(BaseModel):
    aggregate_by: Literal["author", "committer"] = Field(
        description="When grouping for reports, this value controls how to group aggregations",
        default="author",
    )
    identify_by: Literal["name", "email"] = Field(
        description="How to identify the user responsible for commits",
        default="name",
    )
    sort_by: Literal["user", "numeric", "temporal"] = Field(
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
    include_globs: list[str] = Field(
        default=[],
        description="Limit analysis to any blob or tree matching one of the provided glob patterns",
    )
    exclude_globs: list[str] = Field(
        default=[],
        description="Exclude any blob or tree matching one of the provided glob patterns.",
    )
    generated: bool = Field(
        default=False,
        description="If false (default), exclude files commonly generated by package managers, e.g., lock files. Otherwise, these will be ignored in analysis",
    )

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
        elif not self.generated:
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
    path: Path = Field(
        default=Path.cwd(),
        description="The local location of the repository to use for analysis.",
    )
    branch: str | None = Field(
        default=None,
        description="The branch to use for analysis. If not specified, defaults to the 'main' or 'master', in that order.",
    )
    ignore_merges: bool = Field(
        default=False,
        description="Whether to ignore merge commits in contribution analysis",
    )
    ignore_whitespace: bool = Field(
        default=False,
        description="Whether to ignore whitespace changes in contribution analysis",
    )
    use_gitignore: bool = Field(
        default=True,
        description="If true, exclude anything that's in the *current* .gitignore from analysis, even if it was previously in the repository",
    )
    persist_data: bool = Field(
        default=True,
        description="If true, persist commit data locally to speed up future analyses",
    )


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
