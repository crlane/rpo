"""Tests for the Rust extension module.

Mirrors rpo-rust/rpo/tests/globs.rs so both language bindings agree on
path-glob semantics.
"""

import subprocess

import polars as pl
import pytest

import rpo


def _git(repo, *args, **env):
    environ = {
        "GIT_AUTHOR_NAME": "A",
        "GIT_AUTHOR_EMAIL": "a@a.com",
        "GIT_COMMITTER_NAME": "A",
        "GIT_COMMITTER_EMAIL": "a@a.com",
        "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
        **env,
    }
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, env={"PATH": "/usr/bin:/bin", **environ})


@pytest.fixture
def repo(tmp_path):
    """A small repo: a source file, a doc, and a binary-ish asset."""
    _git(tmp_path, "init", "-q", "-b", "main")
    # Neutralize any global gitignore so fixture files are always staged.
    _git(tmp_path, "config", "core.excludesfile", "/dev/null")
    for name, body in [
        ("src/main.py", "print('hi')\n"),
        ("docs/guide.md", "# Guide\n"),
        ("assets/logo.bin", "not really\n"),
    ]:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")
    return str(tmp_path)


def paths(df):
    return sorted(df["path"].to_list())


class TestFrames:
    def test_commits_returns_a_polars_frame(self, repo):
        df = rpo.commits(repo)
        assert isinstance(df, pl.DataFrame)
        assert df.height == 1

    def test_datetimes_are_utc_milliseconds(self, repo):
        df = rpo.commits(repo)
        for col in ("author_time", "commit_time"):
            dtype = df.schema[col]
            assert isinstance(dtype, pl.Datetime)
            assert dtype.time_unit == "ms"

    def test_file_changes_lists_every_path(self, repo):
        assert paths(rpo.file_changes(repo)) == [
            "assets/logo.bin",
            "docs/guide.md",
            "src/main.py",
        ]

    def test_blame_returns_a_frame(self, repo):
        df = rpo.blame(repo)
        assert isinstance(df, pl.DataFrame)
        assert df.height > 0

    def test_analyze_exposes_all_frames(self, repo):
        analysis = rpo.analyze(repo)
        assert isinstance(analysis.commits, pl.DataFrame)
        assert isinstance(analysis.file_changes, pl.DataFrame)
        assert isinstance(analysis.blame, pl.DataFrame)
        assert analysis.skipped_files == []
        assert "Analysis(" in repr(analysis)

    def test_blame_over_time_accepts_a_cadence(self, repo):
        df = rpo.blame_over_time(repo, snapshots="all")
        assert isinstance(df, pl.DataFrame)
        assert "snapshot_time" in df.columns


class TestGlobs:
    """Mirrors rpo-rust/rpo/tests/globs.rs."""

    def test_exclude_globs_drop_matching_paths(self, repo):
        got = paths(rpo.file_changes(repo, exclude_globs=["**/*.bin"]))
        assert got == ["docs/guide.md", "src/main.py"]

    def test_include_globs_restrict_to_matches(self, repo):
        got = paths(rpo.file_changes(repo, include_globs=["src/**"]))
        assert got == ["src/main.py"]

    def test_exclude_wins_over_include(self, repo):
        got = paths(rpo.file_changes(
            repo, include_globs=["src/**", "docs/**"], exclude_globs=["docs/**"]
        ))
        assert got == ["src/main.py"]

    def test_single_star_crosses_directory_separators(self, repo):
        # globset is built without literal_separator, matching the Rust side.
        got = paths(rpo.file_changes(repo, include_globs=["*.py"]))
        assert got == ["src/main.py"]

    def test_globs_apply_to_blame_too(self, repo):
        got = rpo.blame(repo, exclude_globs=["**/*.bin"])
        assert "assets/logo.bin" not in got["path"].to_list()


class TestErrors:
    def test_missing_repository_raises_typed_error(self, tmp_path):
        with pytest.raises(rpo.NotARepositoryError) as exc:
            rpo.commits(str(tmp_path / "nope"))
        assert "not a git repository" in str(exc.value)

    def test_typed_errors_subclass_the_base(self):
        assert issubclass(rpo.NotARepositoryError, rpo.RpoError)
        assert issubclass(rpo.InvalidGlobError, rpo.RpoError)
        assert issubclass(rpo.RevisionNotFoundError, rpo.RpoError)

    def test_invalid_glob_raises_typed_error(self, repo):
        with pytest.raises(rpo.InvalidGlobError) as exc:
            rpo.file_changes(repo, exclude_globs=["["])
        assert "invalid glob" in str(exc.value)

    def test_unknown_snapshot_mode_raises_value_error(self, repo):
        with pytest.raises(ValueError, match="unknown snapshot mode"):
            rpo.blame_over_time(repo, snapshots="fortnightly")
