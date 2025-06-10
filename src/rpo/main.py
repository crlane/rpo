import logging
import os

import click

from rpo.analyzer import RepoAnalyzer
from rpo.models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    DataSelectionOptions,
    FileSelectionOptions,
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
    help="File path glob patterns to INCLUDE. If specified, matching paths will be the only files included in aggregation. If neither --glob nor --xglob are specified, all files will be included in aggregation. Paths are relative to root of repository.",
)
@click.option(
    "--xglob",
    "-xg",
    "exclude_globs",
    type=str,
    multiple=True,
    help="File path glob patterns to EXCLUDE. If specified, matching paths will be filtered before aggregation. If neither --glob nor --xglob are specified, all files will be included in aggregation. Paths are relative to root of repository.",
)
@click.option(
    "--aggregate-by",
    "-A",
    "aggregate_by",
    type=str,
    default="author",
)
@click.option(
    "--identify-by",
    "-I",
    "identify_by",
    type=str,
    default="name",
)
@click.option(
    "--sort-by",
    "-S",
    "sort_by",
    type=str,
    default="actor",
)
@click.option(
    "--alias-file",
    "-a",
    type=click.File(),
    help="A JSON file that maps a contributor name to one or more aliases. Useful in cases where authors have used multiple email addresses, names, or spellings to create commits.",
)
@click.option("--repository", "-r", type=click.Path(exists=True))
@click.option("--branch", "-b", type=str, default=None)
@click.pass_context
def cli(
    ctx: click.Context,
    aggregate_by: AggregateBy,
    identify_by: IdentifyBy,
    sort_by: SortBy,
    repository: str | None = None,
    branch: str | None = None,
    exclude_globs: list[str] | None = None,
    include_globs: list[str] | None = None,
    alias_file: click.File | None = None,
):
    _ = ctx.ensure_object(dict)

    ctx.obj["analyzer"] = RepoAnalyzer(path=repository or os.getcwd(), branch=branch)
    ctx.obj["data_selection"] = DataSelectionOptions(
        aggregate_by=aggregate_by, identify_by=identify_by, sort_by=sort_by
    )
    ctx.obj["file_selection"] = FileSelectionOptions(
        include_globs=include_globs, exclude_globs=exclude_globs
    )


@cli.command()
@click.pass_context
def summary(ctx: click.Context):
    ra = ctx.obj.get("analyzer")
    print(ra.summary(ctx.obj.get("data_selection")))


@cli.command()
@click.pass_context
def revisions(ctx: click.Context):
    """List all revisions in the repository"""
    ra = ctx.obj.get("analyzer")
    print(ra.revs)


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
        print(ra.file_report(options))
    else:
        print(ra.contributor_report(options))


@cli.command()
@click.option("--no-whitespace", "-w", "ignore_whitespace", is_flag=True, default=False)
@click.option("--no-merges", "ignore_merges", is_flag=True, default=False)
@click.option("--revision", "-R", "revision", type=str, default=None)
@click.pass_context
def repo_blame(
    ctx: click.Context,
    revision: str,
    ignore_whitespace: bool,
    ignore_merges: bool,
):
    """Computes the per contributor blame for all files at a given revision. Can be aggregated by contributor or by file.

    Used to see who creates the most
    """
    ra = ctx.obj.get("analyzer")
    options = BlameCmdOptions()
    print(
        ra.blame(
            options,
            rev=revision,
            ignore_whitespace=ignore_whitespace,
            ignore_merges=ignore_merges,
        )
    )
