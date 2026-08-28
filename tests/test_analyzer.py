"""RepoAnalyzer reports, over the synthetic fixture repository."""

import polars as pl
import pytest
from git import Actor
from rpo.analyzer import RepoAnalyzer


class TestFrames:
    def test_exposes_the_raw_frames(self, tmp_repo_analyzer: RepoAnalyzer):
        assert tmp_repo_analyzer.commits.height == 6
        assert tmp_repo_analyzer.file_changes.height > 0
        assert tmp_repo_analyzer.blame is not None
        assert tmp_repo_analyzer.skipped_files == []

    def test_repr_reports_frame_sizes(self, tmp_repo_analyzer: RepoAnalyzer):
        assert "commits=6" in repr(tmp_repo_analyzer)

    def test_walk_options_reach_the_engine(self, tmp_repo):
        everything = RepoAnalyzer(tmp_repo.working_dir)
        filtered = RepoAnalyzer(tmp_repo.working_dir, exclude_globs=["**/*.txt"])
        assert filtered.file_changes.height < everything.file_changes.height


class TestSummary:
    @pytest.mark.parametrize(
        "identify_by,contributors", [("name", 3), ("email", 4)], ids=("name", "email")
    )
    def test_counts_contributors_by_identity(
        self, tmp_repo_analyzer, identify_by, contributors
    ):
        summary = tmp_repo_analyzer.summary(identify_by=identify_by)
        assert summary.height == 1
        assert summary["contributors"][0] == contributors
        assert summary["commits"][0] > 0


class TestActivityReports:
    def test_contributor_report_columns(self, tmp_repo_analyzer: RepoAnalyzer):
        report = tmp_repo_analyzer.contributor_report()
        assert list(report.columns) == [
            "canonical_author_name",
            "commits",
            "insertions",
            "deletions",
            "lines",
            "net",
        ]

    def test_file_report_columns(self, tmp_repo_analyzer: RepoAnalyzer):
        report = tmp_repo_analyzer.file_report()
        assert list(report.columns) == [
            "path",
            "commits",
            "contributors",
            "insertions",
            "deletions",
            "lines",
            "net",
        ]

    def test_reports_sort_by_churn_descending(self, tmp_repo_analyzer: RepoAnalyzer):
        lines = tmp_repo_analyzer.file_report()["lines"].to_list()
        assert lines == sorted(lines, reverse=True)

    def test_limit_truncates(self, tmp_repo_analyzer: RepoAnalyzer):
        assert tmp_repo_analyzer.file_report(limit=1).height == 1

    def test_net_is_signed(self, tmp_repo_analyzer: RepoAnalyzer):
        """The engine's counts are unsigned; net must not wrap around."""
        for report in (
            tmp_repo_analyzer.file_report(),
            tmp_repo_analyzer.contributor_report(),
        ):
            assert report["net"].dtype == pl.Int64


class TestBlame:
    @pytest.mark.parametrize(
        "identify_by,line_count", [("name", 5), ("email", 3)], ids=("name", "email")
    )
    def test_attributes_surviving_lines(
        self,
        tmp_repo_analyzer: RepoAnalyzer,
        actors: list[Actor],
        identify_by: str,
        line_count: int,
    ):
        report = tmp_repo_analyzer.blame_report(identify_by=identify_by)
        owned = dict(zip(report[f"canonical_author_{identify_by}"], report["lines"]))
        assert owned[getattr(actors[-1], identify_by)] == line_count

    def test_cumulative_blame_is_one_row_per_snapshot(self, tmp_repo_analyzer):
        df = tmp_repo_analyzer.cumulative_blame(snapshots="all")
        assert df.columns[0] == "snapshot_time"
        assert df.height > 0

    def test_file_timeline_columns(self, tmp_repo_analyzer: RepoAnalyzer):
        df = tmp_repo_analyzer.file_timeline(snapshots="all")
        assert list(df.columns) == ["snapshot_time", "path", "lines"]


class TestPunchcard:
    def test_grid_shape(self, tmp_repo_analyzer: RepoAnalyzer):
        df = tmp_repo_analyzer.punchcard()
        assert list(df.columns) == ["day", "hour", "count"]
        assert df["count"].sum() == tmp_repo_analyzer.commits.height

    @pytest.mark.parametrize(
        "identifier,identify_by,commits",
        [
            ("updated@example.com", "email", 2),
            ("User2 Lastname", "name", 3),
        ],
    )
    def test_scoped_to_one_contributor(
        self, tmp_repo_analyzer, identifier, identify_by, commits
    ):
        df = tmp_repo_analyzer.punchcard(identifier, identify_by=identify_by)
        assert df["count"].sum() == commits
