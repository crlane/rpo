"""The plotting helpers write PNGs from report frames."""

import polars as pl
import pytest
from rpo import plotting


@pytest.fixture
def blame_df():
    return pl.DataFrame(
        {"canonical_author_name": ["A", "B"], "lines": [10, 5], "files": [2, 1]}
    )


def test_blame_writes_a_png(blame_df, tmp_path):
    out = plotting.blame(blame_df, tmp_path / "blame.png")
    assert out.exists() and out.stat().st_size > 0


def test_creates_missing_parent_directories(blame_df, tmp_path):
    out = plotting.blame(blame_df, tmp_path / "nested" / "dir" / "blame.png")
    assert out.exists()


def test_punchcard_writes_a_png(tmp_path):
    df = pl.DataFrame({"day": [1, 3], "hour": [9, 14], "count": [4, 2]})
    out = plotting.punchcard(df, tmp_path / "punchcard.png")
    assert out.exists() and out.stat().st_size > 0


def test_cumulative_blame_unpivots_wide_input(tmp_path):
    df = pl.DataFrame(
        {
            "snapshot_time": pl.Series([1, 2], dtype=pl.Datetime(time_unit="ms")),
            "A": [1, 2],
            "B": [3, 4],
        }
    )
    out = plotting.cumulative_blame(df, tmp_path / "cblame.png")
    assert out.exists() and out.stat().st_size > 0


def test_file_churn_respects_top(tmp_path):
    df = pl.DataFrame({"path": list("abcde"), "lines": [5, 4, 3, 2, 1]})
    out = plotting.file_churn(df, tmp_path / "churn.png", top=2)
    assert out.exists() and out.stat().st_size > 0
