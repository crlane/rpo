"""Chart helpers for the report frames.

Each function takes a report DataFrame and writes a PNG, returning the
path. They are deliberately explicit — nothing plots as a side effect of
running a report.

Charts are rendered with Altair through `polars.DataFrame.plot`.
"""

import logging
from pathlib import Path

import altair as alt
import polars as pl
from polars import DataFrame

logger = logging.getLogger(__name__)

DEFAULT_PPI = 200

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _save(chart, output: str | Path) -> Path:
    out = Path(output)
    if out.parent != Path():
        out.parent.mkdir(parents=True, exist_ok=True)
    chart.save(out, ppi=DEFAULT_PPI)
    logger.info("wrote %s", out)
    return out


def blame(
    df: DataFrame,
    output: str | Path = "blame.png",
    *,
    title: str = "Lines owned at HEAD",
) -> Path:
    """Horizontal bar chart of `RepoAnalyzer.blame_report()`."""
    identity = df.columns[0]
    chart = df.plot.bar(x="lines:Q", y=f"{identity}:N").properties(title=title)
    return _save(chart, output)


def cumulative_blame(
    df: DataFrame,
    output: str | Path = "cumulative_blame.png",
    *,
    title: str = "Cumulative blame",
) -> Path:
    """Stacked area chart of `RepoAnalyzer.cumulative_blame()`.

    That report is one column per contributor, which Altair cannot stack
    directly, so it is unpivoted back to long form first.
    """
    long = df.unpivot(
        index="snapshot_time", variable_name="contributor", value_name="lines"
    )
    chart = long.plot.area(
        x="snapshot_time:T", y="lines:Q", color="contributor:N"
    ).properties(title=title)
    return _save(chart, output)


def punchcard(
    df: DataFrame,
    output: str | Path = "punchcard.png",
    *,
    title: str = "Commit punchcard",
) -> Path:
    """Day/hour bubble chart of `RepoAnalyzer.punchcard()`."""
    named = df.with_columns(
        pl.col("day")
        .replace_strict({i + 1: name for i, name in enumerate(DAY_NAMES)})
        .alias("day_name")
    )
    chart = named.plot.circle(
        x="hour:O",
        y=alt.Y("day_name:N", sort=DAY_NAMES, title="day"),
        size="count:Q",
        color="count:Q",
    ).properties(title=title)
    return _save(chart, output)


def file_churn(
    df: DataFrame,
    output: str | Path = "file_churn.png",
    *,
    top: int = 20,
    title: str = "Most-changed files",
) -> Path:
    """Bar chart of the busiest files from `RepoAnalyzer.file_report()`."""
    chart = df.head(top).plot.bar(x="lines:Q", y="path:N").properties(title=title)
    return _save(chart, output)
