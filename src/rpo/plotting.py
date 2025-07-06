import logging
import time
from pathlib import Path

from polars import DataFrame

from .models import PlotOptions
from .types import SupportedPlotType

logger = logging.getLogger(__name__)

DEFAULT_PPI = 200


class Plotter:
    def __init__(
        self,
        df: DataFrame,
        options: PlotOptions,
        plot_type: SupportedPlotType,
        **kwargs,
    ):
        self.df = df
        self.location: Path = Path(options.img_location)
        _ = self.location.mkdir(exist_ok=True, parents=True)
        self.plot_type = plot_type
        self.plot_args = kwargs

    def plot(self):
        if self.plot_type == "cumulative_blame":
            out = self._plot_cumulative_blame()
        elif self.plot_type == "blame":
            out = self._plot_blame()
        elif self.plot_type == "punchcard":
            out = self._plot_punchcard()
        else:
            raise ValueError("Unsupported plot type")

        logger.info(f"File written to {out}")

    def _plot_blame(self) -> Path:
        chart = self.df.plot.bar(
            x=self.plot_args.get("x", "lines:Q"),
            y=self.plot_args.get("y", "author_name"),
        ).properties(title=self.plot_args.get("title", "Blame"))

        filename = self.plot_args.get("filename", f"repo_blame_{time.time()}")
        output = self.location / f"{filename}.png"
        chart.save(output, ppi=DEFAULT_PPI)
        return output

    def _plot_cumulative_blame(
        self,
    ) -> Path:
        # see https://altair-viz.github.io/user_guide/marks/area.html
        chart = self.df.plot.area(
            x=self.plot_args.get("x", "datetime:T"),
            y=self.plot_args.get("y", "sum(lines):Q"),
            color=self.plot_args.get(
                "color",
            ),  # f"{options.group_by_key}:N",
        ).properties(
            title=self.plot_args.get("title", "Cumulative Blame"),
        )
        filename = self.plot_args.get("filename", f"cumulative_blame_{time.time()}")
        output = self.location / f"{filename}.png"
        chart.save(output, ppi=DEFAULT_PPI)
        return output

    def _plot_punchcard(self) -> Path:
        # see https://altair-viz.github.io/user_guide/marks/area.html
        title = self.plot_args.pop("title", "Author Punchcard")
        filename = self.plot_args.pop("filename", f"punchcard_{time.time()}")
        chart = self.df.plot.circle(**self.plot_args).properties(title=title)
        output = self.location / f"{filename}.png"
        chart.save(output, ppi=DEFAULT_PPI)
        return output
