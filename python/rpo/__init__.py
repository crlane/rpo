"""rpo — git repository participation analysis.

The analysis engine is the `rpo` Rust crate, reached through the private
`rpo._rpo` extension module. Walking history and building the frames
happens in Rust; everything here is polars on top of the results.

Two levels of API:

- `RepoAnalyzer` — walk once, then run reports over the frames.
- `commits`, `file_changes`, `blame`, `blame_over_time`, `analyze` —
  the raw frames, mirroring the Rust builder's terminals.

>>> import rpo
>>> ra = rpo.RepoAnalyzer(".", exclude_globs=["docs/**"])
>>> ra.contributor_report(identify_by="email")
"""

from rpo._rpo import (
    Analysis,
    InvalidGlobError,
    NotARepositoryError,
    RevisionNotFoundError,
    RpoError,
    analyze,
    blame,
    blame_over_time,
    commits,
    file_changes,
)

from . import plotting
from .analyzer import RepoAnalyzer
from .models import AggregateBy, IdentifyBy, Snapshots, group_column

__version__ = "0.1.0b3"

__all__ = [
    "AggregateBy",
    "Analysis",
    "IdentifyBy",
    "InvalidGlobError",
    "NotARepositoryError",
    "RepoAnalyzer",
    "RevisionNotFoundError",
    "RpoError",
    "Snapshots",
    "__version__",
    "analyze",
    "blame",
    "blame_over_time",
    "commits",
    "file_changes",
    "group_column",
    "plotting",
]
