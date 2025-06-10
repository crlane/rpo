import pytest
from git import Actor

from rpo.analyzer import RepoAnalyzer
from rpo.models import BlameCmdOptions, SummaryCmdOptions


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
    file_report = tmp_repo_analyzer.file_report().to_dict(as_series=False)
    assert list(file_report.keys()) == [
        "filename",
        "author_name",
        "insertions",
        "deletions",
        "lines",
    ]
    assert file_report


def test_contributor_report(tmp_repo_analyzer: RepoAnalyzer):
    contributor_report = tmp_repo_analyzer.contributor_report().to_dict(as_series=False)
    assert list(contributor_report.keys()) == [
        "author_name",
        "insertions",
        "deletions",
        "lines",
    ]
    # author 1, added one file with one line, deletes file
    assert contributor_report["insertions"][0] == 1
    assert contributor_report["deletions"][0] == 1
    assert contributor_report["lines"][0] == 2

    # author 2, addes one file with two lines, leaves file
    assert contributor_report["insertions"][1] == 2
    assert contributor_report["deletions"][1] == 0.0
    assert contributor_report["lines"][1] == 2.0

    # author 3, adds one file with three lines, duplicates contents, then truncates, leaves it
    assert contributor_report["insertions"][2] == 6.0
    assert contributor_report["deletions"][2] == 1.0
    assert contributor_report["lines"][2] == 7.0


@pytest.mark.parametrize(
    "identify_by,lines_count",
    [("name", 3), ("email", 4)],
    ids=("by-name", "by-email"),
)
def test_blame(
    tmp_repo_analyzer: RepoAnalyzer,
    actors: list[Actor],
    identify_by: str,
    lines_count: int,
):
    options = BlameCmdOptions(identify_by=identify_by)
    blame_report = tmp_repo_analyzer.blame(options).to_dict(as_series=False)
    assert blame_report
