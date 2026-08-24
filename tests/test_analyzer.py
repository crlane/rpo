from typing import LiteralString

import polars as pl
import pytest
from git import Actor
from git.repo import Repo

from rpo.analyzer import RepoAnalyzer
from rpo.models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    BusFactorCmdOptions,
    GitOptions,
    PunchcardCmdOptions,
    RevisionsCmdOptions,
    SummaryCmdOptions,
)



@pytest.mark.parametrize(
    "identify_by,contrib_count",
    [("name", 3), ("email", 4)],
    ids=("by-name", "by-email"),
)
def test_summary(tmp_repo_analyzer: RepoAnalyzer, identify_by: str, contrib_count: int):
    options = SummaryCmdOptions(identify_by=identify_by)
    summary = tmp_repo_analyzer.summary(options)
    assert summary is not None
    summary_dict = summary.to_dict(as_series=False)
    assert summary_dict["files"] == [3]
    assert summary_dict["contributors"] == [contrib_count]
    assert summary_dict["commits"] == [6]


def test_file_report(tmp_repo_analyzer: RepoAnalyzer):
    file_report = tmp_repo_analyzer.file_report(
        ActivityReportCmdOptions(aggregate_by="author", sort_by="numeric")
    ).to_dict(as_series=False)
    assert list(file_report.keys()) == [
        "path",
        "insertions",
        "deletions",
        "lines",
        "net",
    ]
    assert file_report


def test_contributor_report(tmp_repo_analyzer: RepoAnalyzer):
    contributor_report = tmp_repo_analyzer.contributor_report(
        ActivityReportCmdOptions(
            sort_by="user", identify_by="name", aggregate_by="author", limit=0
        )
    ).to_dict(as_series=False)
    assert list(contributor_report.keys()) == [
        "canonical_author_name",
        "insertions",
        "deletions",
        "lines",
        "net",
    ]
    # author 1, added one file with one line, deletes file
    assert contributor_report["insertions"][0] == 1, "First author insertions mismatch"
    assert contributor_report["deletions"][0] == 1, "First author deletions mismatch"
    assert contributor_report["lines"][0] == 2, "First author lines changed mismatch"
    assert contributor_report["net"][0] == 0, "First author net mismatch"

    # author 2, addes one file with two lines, leaves file
    assert contributor_report["insertions"][1] == 2
    assert contributor_report["deletions"][1] == 0.0
    assert contributor_report["lines"][1] == 2.0

    # author 3, adds one file with three lines, duplicates contents, then truncates, leaves it
    assert contributor_report["insertions"][2] == 6.0
    assert contributor_report["deletions"][2] == 1.0
    assert contributor_report["lines"][2] == 7.0


@pytest.mark.parametrize(
    "identify_by,line_count",
    [("name", 5), ("email", 3)],
    ids=("by-name", "by-email"),
)
def test_blame(
    tmp_repo_analyzer: RepoAnalyzer,
    actors: list[Actor],
    identify_by: str,
    line_count: int,
):
    options = BlameCmdOptions(identify_by=identify_by)
    blame_report = tmp_repo_analyzer.blame(options).to_dict(as_series=False)
    flattened = dict(
        zip(blame_report[f"canonical_author_{identify_by}"], blame_report["lines"])
    )
    actor = actors[-1]
    assert flattened[getattr(actor, identify_by)] == line_count


def test_bus_factor(tmp_repo_analyzer):
    _ = tmp_repo_analyzer.bus_factor(BusFactorCmdOptions())
    assert True


@pytest.mark.parametrize(
    "identifier,identify_by,aggregate_by,slots,commits",
    [
        ("updated@example.com", "email", "author", 2, 2),
        ("User2 Lastname", "name", "author", 2, 3),
        ("updated@example.com", "email", "committer", 2, 2),
        ("User2 Lastname", "name", "committer", 2, 3),
    ],
)
def test_punchcard(
    tmp_repo_analyzer,
    identifier: str,
    identify_by: LiteralString,
    aggregate_by: str,
    slots: int,
    commits: int,
):
    """A punchcard is a (day-of-week, hour) grid of commit counts."""
    df = tmp_repo_analyzer.punchcard(
        PunchcardCmdOptions(
            identifier=identifier,
            identify_by=identify_by,
            aggregate_by=aggregate_by,
        )
    )
    assert list(df.columns) == ["day", "hour", "count"]
    assert df.height == slots, "occupied day/hour slots"
    assert df["count"].sum() == commits, "total commits"


def test_revisions(tmp_repo_analyzer):
    res = tmp_repo_analyzer.revisions(RevisionsCmdOptions())

    assert res.height == 6, "Number of revisions incorrect"


def test_net_is_signed_when_deletions_exceed_insertions(tmp_repo_analyzer):
    """The engine's counts are unsigned; net must not wrap around."""
    report = tmp_repo_analyzer.file_report(
        ActivityReportCmdOptions(aggregate_by="author")
    )
    assert report["net"].dtype == pl.Int64, (
        "net must be signed; unsigned subtraction wraps a net loss to ~1.8e19"
    )
    # Same for the contributor view.
    contributors = tmp_repo_analyzer.contributor_report(
        ActivityReportCmdOptions(aggregate_by="author")
    )
    assert contributors["net"].dtype == pl.Int64
