"""rpo — git repository participation analysis.

The heavy lifting (walking history, building the frames) happens in the
Rust `rpo` crate via the private `rpo._rpo` extension module. Everything
here returns polars DataFrames.
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

__version__ = "0.2.0a1"

__all__ = [
    "Analysis",
    "InvalidGlobError",
    "NotARepositoryError",
    "RevisionNotFoundError",
    "RpoError",
    "__version__",
    "analyze",
    "blame",
    "blame_over_time",
    "commits",
    "file_changes",
]
