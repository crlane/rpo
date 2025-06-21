from pathlib import Path
from unittest.mock import Mock

import pytest
from polars import DataFrame

from rpo.writer import Writer


@pytest.mark.parametrize(
    "paths, counts",
    [
        (("-"), (0, 0)),
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
def test_writer(paths, counts, monkeypatch, tmp_path, capsys):
    mocks = {}
    functions = ["write_csv", "write_json"]
    for f in functions:
        mocks[f] = Mock(name=f)
        monkeypatch.setattr(DataFrame, f, mocks[f])
    paths = [tmp_path / p if p != "-" else Path(p) for p in paths]

    df = DataFrame(range(10))
    writer = Writer(paths)
    writer.write(df)
    actual_counts = tuple(mock.call_count for mock in mocks.values())
    assert counts == actual_counts
    if actual_counts == (0, 0):
        assert capsys.readouterr().out


def test_output_unsupported(tmp_path):
    writer = Writer([tmp_path / "foo.xls"])
    with pytest.raises(ValueError, match="Unsupported filetype"):
        writer.write(DataFrame())
