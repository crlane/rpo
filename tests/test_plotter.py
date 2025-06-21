import pytest
from polars import DataFrame

from rpo.plotting import Plotter


@pytest.fixture
def plotter(tmp_path):
    return Plotter(
        tmp_path,
        DataFrame({"a": range(10), "b": range(10, 20)}),
        plot_type="blame",
        x="a:Q",
        y="b:N",
    )


def test_calls_correct_function(plotter):
    plotter.plot_type = "violin"
    with pytest.raises(ValueError, match="Unsupported plot type"):
        plotter.plot()
