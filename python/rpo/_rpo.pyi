"""Type stubs for the Rust extension module."""

from typing import Literal

import polars as pl

Snapshots = Literal["head", "tags", "daily", "weekly", "monthly", "all"]

class RpoError(Exception):
    """Base class for every error raised by the Rust engine."""

class NotARepositoryError(RpoError):
    """The given path is not a git repository."""

class InvalidGlobError(RpoError):
    """A path glob failed to parse."""

class RevisionNotFoundError(RpoError):
    """The requested revision does not exist in the repository."""

class Analysis:
    """The frames produced by a single walk of a repository."""

    @property
    def commits(self) -> pl.DataFrame: ...
    @property
    def file_changes(self) -> pl.DataFrame: ...
    @property
    def blame(self) -> pl.DataFrame | None: ...
    @property
    def blame_over_time(self) -> pl.DataFrame | None: ...
    @property
    def skipped_files(self) -> list[str]: ...

def commits(
    path: str,
    *,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    ignore_merges: bool = True,
    first_parent_only: bool = False,
    ignore_bots: bool = False,
) -> pl.DataFrame: ...
def file_changes(
    path: str,
    *,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    ignore_merges: bool = True,
    first_parent_only: bool = False,
    ignore_bots: bool = False,
) -> pl.DataFrame: ...
def blame(
    path: str,
    *,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    ignore_merges: bool = True,
    first_parent_only: bool = False,
    ignore_bots: bool = False,
) -> pl.DataFrame: ...
def blame_over_time(
    path: str,
    *,
    snapshots: Snapshots = "monthly",
    revisions: list[str] | None = None,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    ignore_merges: bool = True,
    first_parent_only: bool = False,
    ignore_bots: bool = False,
) -> pl.DataFrame: ...
def analyze(
    path: str,
    *,
    snapshots: Snapshots = "head",
    revisions: list[str] | None = None,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    ignore_merges: bool = True,
    first_parent_only: bool = False,
    ignore_bots: bool = False,
) -> Analysis: ...
