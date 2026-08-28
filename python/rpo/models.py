"""Typed vocabulary shared by the analyzer and the plotting helpers.

These mirror the Rust library's `rpo::options` types. Walk-time settings
belong on `RepoAnalyzer`; report-time settings are keyword arguments on
the report methods.
"""

from typing import Literal

type AggregateBy = Literal["author", "committer"]
"""Whose identity to attribute work to."""

type IdentifyBy = Literal["name", "email"]
"""Which field uniquely names a person."""

type Snapshots = Literal["head", "tags", "daily", "weekly", "monthly", "all"]
"""Cadence for blame-over-time snapshots."""


def group_column(aggregate_by: AggregateBy, identify_by: IdentifyBy) -> str:
    """The frame column an (aggregate_by, identify_by) pair groups on.

    The engine canonicalizes identities through `.mailmap`, so reports
    always group on the `canonical_*` columns rather than the raw ones.
    """
    return f"canonical_{aggregate_by}_{identify_by}"
