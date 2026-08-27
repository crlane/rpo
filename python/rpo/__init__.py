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

import importlib

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

from .analyzer import RepoAnalyzer
from .models import AggregateBy, IdentifyBy, Snapshots, group_column

__version__ = "0.1.0b3"


def __getattr__(name: str):
    """Import `rpo.plotting` on first use.

    Charting pulls in Altair, which is a heavier dependency than the
    analysis itself needs. Deferring it keeps `import rpo` working in
    environments that only want the frames.
    """
    if name == "plotting":
        # importlib, not `from . import plotting`: the latter re-enters
        # this function and recurses forever.
        return importlib.import_module(".plotting", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
