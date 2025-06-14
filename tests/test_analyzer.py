from unittest.mock import Mock

import pytest
from git import Actor
from git.repo import Repo
from polars import DataFrame

from rpo.analyzer import RepoAnalyzer
from rpo.models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    BusFactorCmdOptions,
    DataSelectionOptions,
    GitOptions,
    PunchcardCmdOptions,
    SummaryCmdOptions,
)


def test_fail_no_path_no_repo():
    with pytest.raises(ValueError, match="Must specify either") as e:
        _ = RepoAnalyzer()


@pytest.mark.parametrize(
    "options, branches, expected",
    [
        (GitOptions(), ("foo", "bar", "main"), "main"),
        (GitOptions(), ("foo", "bar", "master"), "master"),
        (GitOptions(), ("master", "main"), "main"),
        (GitOptions(branch="master"), ("master", "main"), "master"),
        (
            GitOptions(branch="foo"),
            (
                "master",
                "main",
                "foo",
                "bar",
            ),
            "foo",
        ),
    ],
    ids=[
        "main-no-master",
        "master-no-main",
        "prefer-main-over-master",
        "specified-master",
        "specified-other",
    ],
)
def test_default_branch(
    options: GitOptions, branches: list[str], expected: str, monkeypatch, tmp_repo
):
    class MockRepo:
        def __init__(self, name):
            self.name = name

    mock_branches = [MockRepo(b) for b in branches]
    monkeypatch.setattr(Repo, "branches", mock_branches)
    ra = RepoAnalyzer(repo=tmp_repo, options=options)
    assert ra.default_branch == expected


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
        "filename",
        "lines",
        "insertions",
        "deletions",
        "net",
    ]
    assert file_report


def test_contributor_report(tmp_repo_analyzer: RepoAnalyzer):
    contributor_report = tmp_repo_analyzer.contributor_report(
        ActivityReportCmdOptions(sort_by="author_name", limit=0)
    ).to_dict(as_series=False)
    assert list(contributor_report.keys()) == [
        "author_name",
        "lines",
        "insertions",
        "deletions",
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


@pytest.mark.parametrize(
    "paths, counts",
    [
        ((), (0, 0)),
        (("foo.json",), (0, 1)),
        (
            (
                "foo.csv",
                "foo.json",
            ),
            (1, 1),
        ),
    ],
    ids=["empty-produces-stdout", "single-json", "json-and-csv"],
)
def test_output(paths, counts, tmp_repo_analyzer, monkeypatch, tmp_path, capsys):
    mocks = {}
    functions = ["write_csv", "write_json"]
    for f in functions:
        mocks[f] = Mock(name=f)
        monkeypatch.setattr(DataFrame, f, mocks[f])
    paths = [tmp_path / p for p in paths]

    df = DataFrame(range(10))
    tmp_repo_analyzer.output(df, paths)
    actual_counts = tuple(mock.call_count for mock in mocks.values())
    assert counts == actual_counts
    if actual_counts == (0, 0):
        assert capsys.readouterr().out


def test_output_unsupported(tmp_repo_analyzer, tmp_path):
    with pytest.raises(ValueError, match="Unsupported filetype"):
        tmp_repo_analyzer.output(DataFrame(), [tmp_path / "foo.xls"])


def test_bus_factor(tmp_repo_analyzer):
    with pytest.raises(NotImplementedError):
        tmp_repo_analyzer.bus_factor(BusFactorCmdOptions())


def test_punchcard(tmp_repo_analyzer):
    df = tmp_repo_analyzer.punchcard(
        PunchcardCmdOptions(identifier="updated@example.com")
    )
    assert True


def test_revisions(tmp_repo_analyzer):
    assert tmp_repo_analyzer.revisions(DataSelectionOptions()).height == 6, (
        "Number of revisions incorrect"
    )
