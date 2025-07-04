import pytest
from polars import DataFrame

from rpo.models import PlotOptions
from rpo.plotting import Plotter


@pytest.fixture
def plotter(tmp_path):
    return Plotter(
        DataFrame({"a": range(10), "b": range(10, 20)}),
        PlotOptions(visualize=True, img_location=tmp_path),
        plot_type="blame",
        x="a:Q",
        y="b:N",
    )


def test_calls_correct_function(plotter):
    plotter.plot_type = "violin"
    with pytest.raises(ValueError, match="Unsupported plot type"):
        plotter.plot()
