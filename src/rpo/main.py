import logging
import os
from collections.abc import Iterable
from pathlib import Path

import click

from rpo.analyzer import RepoAnalyzer
from rpo.models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    DataSelectionOptions,
    FileSelectionOptions,
    GitOptions,
)
from rpo.types import AggregateBy, IdentifyBy, SortBy

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", logging.INFO),
    format="[%(asctime)s] %(levelname)s: %(name)s.%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S.%s",
)
logger = logging.getLogger(__name__)


@click.group("rpo")
@click.option(
    "--glob",
    "-g",
    "include_globs",
    type=str,
    multiple=True,
    help="File path glob patterns to INCLUDE. If specified, matching paths will be the only files included in aggregation.\
            If neither --glob nor --xglob are specified, all files will be included in aggregation. Paths are relative to root of repository.",
)
@click.option(
    "--xglob",
    "-xg",
    "exclude_globs",
    type=str,
    multiple=True,
    help="File path glob patterns to EXCLUDE. If specified, matching paths will be filtered before aggregation.\
            If neither --glob nor --xglob are specified, all files will be included in aggregation. Paths are relative to root of repository.",
)
@click.option(
    "--aggregate-by",
    "-A",
    "aggregate_by",
    type=str,
    help="Controls the field used to aggregate data",
    default="author",
)
@click.option(
    "--identify-by",
    "-I",
    "identify_by",
    type=str,
    help="Controls the field used to identify auhors.",
    default="name",
)
@click.option(
    "--sort-by",
    "-S",
    "sort_by",
    type=str,
    help="Controls the field used to sort output",
    default="actor",
)
@click.option(
    "--alias-file",
    "-a",
    type=click.File(),
    help="Not currently used. A JSON file that maps a contributor name to one or more aliases.\
            Useful in cases where authors have used multiple email addresses, names, or spellings to create commits.",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=("stdout",),
    multiple=True,
    help="Path of the output file; format is determined by the filename extension.",
)
@click.option("--repository", "-r", type=click.Path(exists=True), default=Path.cwd())
@click.option("--branch", "-b", type=str, default=None)
@click.option(
    "--allow-dirty",
    is_flag=True,
    default=False,
    help="Proceed with analyis even if repository has uncommitted changes",
)
@click.pass_context
def cli(
    ctx: click.Context,
    aggregate_by: AggregateBy,
    identify_by: IdentifyBy,
    sort_by: SortBy,
    repository: str | None = None,
    branch: str | None = None,
    allow_dirty: bool = False,
    exclude_globs: list[str] | None = None,
    include_globs: list[str] | None = None,
    ignore_whitespace: bool = False,
    ignore_generated_files: bool = False,
    ignore_merges: bool = False,
    output: Iterable[Path | str] = ("stdout"),
    alias_file: click.File | None = None,
):
    _ = ctx.ensure_object(dict)

    ctx.obj["analyzer"] = RepoAnalyzer(
        path=repository or Path.cwd(),
        options=GitOptions(
            branch=branch,
            allow_dirty=allow_dirty,
            ignore_whitespace=ignore_whitespace,
            ignore_generated_files=ignore_generated_files,
            ignore_merges=ignore_merges,
        ),
    )
    ctx.obj["data_selection"] = DataSelectionOptions(
        aggregate_by=aggregate_by, identify_by=identify_by, sort_by=sort_by
    )
    ctx.obj["file_selection"] = FileSelectionOptions(
        include_globs=include_globs, exclude_globs=exclude_globs
    )
    ctx.obj["file_output"] = output


@cli.command()
@click.pass_context
def summary(ctx: click.Context):
    """Generate very high level summary for the repository"""
    ra = ctx.obj.get("analyzer")
    summary_df = ra.summary(ctx.obj.get("data_selection"))
    ra.output(summary_df, ctx.obj.get("file_output"))


@cli.command()
@click.pass_context
def revisions(ctx: click.Context):
    """List all revisions in the repository"""
    ra = ctx.obj.get("analyzer")
    ra.output(ra.revs, ctx.obj.get("file_output"))


@cli.command()
@click.pass_context
@click.option(
    "--files-report",
    "-f",
    "files_report",
    is_flag=True,
    default=False,
    help="If set, produce file activity report. If not set, activity is by author",
)
def activity_report(ctx: click.Context, files_report: bool):
    """Simple commit report aggregated by author or committer"""
    ra = ctx.obj.get("analyzer")
    options = ActivityReportCmdOptions(
        **dict(ctx.obj.get("file_selection")), **dict(ctx.obj.get("data_selection"))
    )
    if files_report:
        report_df = ra.file_report(options)
    else:
        report_df = ra.contributor_report(options)

    ra.output(report_df, ctx.obj.get("file_output"))


@cli.command()
@click.option("--revision", "-R", "revision", type=str, default=None)
@click.option(
    "--plot",
    "-p",
    "plot",
    type=click.Path(),
    help="Directory to write a bar chart image of the blame data",
)
@click.pass_context
def repo_blame(ctx: click.Context, revision: str, plot: Path | None = None):
    """Computes the per contributor blame for all files at a given revision. Can be aggregated by contributor or by file.

    Used to see who creates the most
    """
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = BlameCmdOptions(
        **dict(ctx.obj.get("file_selection")), **dict(ctx.obj.get("data_selection"))
    )
    blame_df = ra.blame(options, rev=revision)
    ra.output(blame_df, ctx.obj.get("file_output"))
    if plot:
        chart = blame_df.plot.bar(x="line_count:Q", y=options.group_by_key)
        if isinstance(plot, str):
            plot = Path(plot)
        if not plot.name.endswith(".png"):
            plot.mkdir(exist_ok=True, parents=True)
            plot = plot / f"{ra.path.name}_blame_by_{options.group_by_key}.png"
        chart.save(plot, ppi=200)
