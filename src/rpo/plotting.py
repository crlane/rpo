import logging
import time
from os import PathLike
from pathlib import Path

from polars import DataFrame

from rpo.types import SupportedPlotType

logger = logging.getLogger(__name__)

DEFAULT_PPI = 200


class Plotter:
    def __init__(
        self,
        location: PathLike[str],
        df: DataFrame,
        plot_type: SupportedPlotType,
        **kwargs,
    ):
        self.location = Path(location)

        self.plot_type = plot_type
        self.df = df
        self.plot_args = kwargs

    def plot(self):
        if self.location.name.endswith(".png"):
            _ = self.location.parent.mkdir(exist_ok=True, parents=True)
        else:
            _ = self.location.mkdir(exist_ok=True, parents=True)
        if self.plot_type == "cumulative_blame":
            self._plot_cumulative_blame()
        elif self.plot_type == "blame":
            self._plot_blame()
        elif self.plot_type == "punchcard":
            self._plot_punchcard()
        else:
            raise ValueError("Unsupported plot type")

        logger.info(f"File written to {self.location}")

    def _plot_blame(self):
        chart = self.df.plot.bar(
            x=self.plot_args.get("x", "lines:Q"),
            y=self.plot_args.get("y", "author_name"),
        ).properties(title=self.plot_args.get("title", "Blame"))
        if not self.location.name.endswith(".png"):
            self.location = self.location / self.plot_args.get(
                "filename", f"repo_blame_{time.time()}.png"
            )
        chart.save(self.location, ppi=DEFAULT_PPI)

    def _plot_cumulative_blame(
        self,
    ):
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
        if not self.location.name.endswith(".png"):
            self.location = self.location / self.plot_args.get(
                "filename", f"cumulative_blame_{time.time()}.png"
            )
        chart.save(self.location, ppi=DEFAULT_PPI)

    def _plot_punchcard(self):
        # see https://altair-viz.github.io/user_guide/marks/area.html
        title = self.plot_args.pop("title", "Author Punchcard")
        filename = self.plot_args.pop("filename", f"punchcard_{time.time()}.png")
        chart = self.df.plot.circle(**self.plot_args).properties(title=title)
        if not self.location.name.endswith(".png"):
            self.location = self.location / filename
        chart.save(self.location, ppi=DEFAULT_PPI)
