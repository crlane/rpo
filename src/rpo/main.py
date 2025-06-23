import json
import logging
from collections.abc import Iterable
from os import PathLike, getenv
from pathlib import Path
from typing import Literal

import click
from click_option_group import optgroup

from rpo.analyzer import RepoAnalyzer
from rpo.models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    GitOptions,
    PunchcardCmdOptions,
    RevisionsCmdOptions,
    SummaryCmdOptions,
)
from rpo.types import AggregateBy, IdentifyBy, SortBy

logging.basicConfig(
    level=getenv("LOG_LEVEL", logging.INFO),
    format="[%(asctime)s] %(levelname)s: %(name)s.%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S.%s",
)
logger = logging.getLogger(__name__)


@click.group("rpo")
@click.option("--repository", "-r", type=click.Path(exists=True), default=Path.cwd())
@click.option("--branch", "-b", type=str, default=None)
@click.option(
    "--allow-dirty",
    is_flag=True,
    default=False,
    help="Proceed with analyis even if repository has uncommitted changes",
)
@optgroup(
    "File selection",
    help="Give you control over which files should be included in your analysis",
)
@optgroup.option(
    "--glob",
    "-g",
    "include_globs",
    type=str,
    multiple=True,
    help="File path glob patterns to INCLUDE. If specified, matching paths will be the only files included in aggregation.\
            If neither --glob nor --xglob are specified, all files will be included in aggregation. Paths are relative to root of repository.",
)
@optgroup.option(
    "--xglob",
    "-xg",
    "exclude_globs",
    type=str,
    multiple=True,
    help="File path glob patterns to EXCLUDE. If specified, matching paths will be filtered before aggregation.\
            If neither --glob nor --xglob are specified, all files will be included in aggregation. Paths are relative to root of repository.",
)
@optgroup.option(
    "--exclude-generated",
    "exclude_generated",
    is_flag=True,
    default=False,
    help="If set, exclude common generated files like package-manager generated lock files from analysis",
)
@optgroup(
    "Data selection", help="Control over how repository data is aggregated and sorted"
)
@optgroup.option(
    "--aggregate-by",
    "-A",
    "aggregate_by",
    type=str,
    help="Controls the field used to aggregate data",
    default="author",
)
@optgroup.option(
    "--identify-by",
    "-I",
    "identify_by",
    type=str,
    help="Controls the field used to identify auhors.",
    default="name",
)
@optgroup.option(
    "--sort-by",
    "-S",
    "sort_by",
    type=str,
    help="Controls the field used to sort output",
    default="user",
)
@optgroup("Plot options", help="Control plot output, if available")
@optgroup.option(
    "--plot",
    "-p",
    "img_location",
    type=click.Path(dir_okay=True, file_okay=True),
    help="The directory where plot output visualization will live. Either a filename ending with '.png' or a directory.",
)
@optgroup("Output options", help="Control how data is displayed or saved")
@optgroup.option(
    "--output-to",
    "-o",
    type=click.Path(dir_okay=False),
    multiple=True,
    help="Save the report data to the path provided; format is determined by the filename extension,\
            which must be one of (.json|.csv). If no save-as path is provided, the report will be printed to stdout",
)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(readable=True, dir_okay=False),
    help="The location of the json formatted config file to use. Defaults to a hidden config.json file in the current working directory. If it exists, then options in the config file take precedence over command line flags.",
)
@click.option(
    "--persist/--no-persist",
    is_flag=True,
    type=bool,
    default=False,
    help="Should the analysis be persisted to disk in a temporary location for reuse",
)
@click.pass_context
def cli(
    ctx: click.Context,
    repository: str | None = None,
    branch: str | None = None,
    allow_dirty: bool = False,
    ignore_whitespace: bool = False,
    ignore_merges: bool = False,
    aggregate_by: AggregateBy = "author",
    identify_by: IdentifyBy = "name",
    sort_by: SortBy = "user",
    exclude_globs: list[str] | None = None,
    include_globs: list[str] | None = None,
    exclude_generated: bool = False,
    img_location: PathLike[str] | None = None,
    output_to: Iterable[PathLike[str]] | None = None,
    exclude_users: list[str] | None = None,
    aliases: dict[str, str] | None = None,
    limit: int | None = None,
    config_file: PathLike[str] | None = None,
    persist: bool = False,
):
    _ = ctx.ensure_object(dict)

    if not config_file:
        default_xdg = Path.home() / ".config" / "rpo" / "config.json"
        for cfg in [default_xdg, Path.cwd() / ".rpo.config.json"]:
            if cfg.exists():
                config_file = cfg
                logger.warning(f"Using config file at {config_file}")
                break
        else:
            logger.warning("No config file found, using defaults and/or cmd line flags")

    if config_file:
        with open(config_file, "r") as f:
            config = json.load(f)

        allow_dirty = config.get("allow_dirty", allow_dirty)
        ignore_whitespace = config.get("ignore_whitespace", ignore_whitespace)
        ignore_merges = config.get("ignore_merges", ignore_merges)

        aggregate_by = config.get("aggregate_by", aggregate_by)
        sort_by = config.get("sort_by", sort_by)
        identify_by = config.get("identify_by", identify_by)

        include_globs = config.get("include_globs", include_globs)
        exclude_globs = config.get("exclude_globs", exclude_globs)
        exclude_generated = config.get("exclude_generated", exclude_generated)

        exclude_users = config.get("exclude_users", [])
        aliases = config.get("aliases", {})
        limit = config.get("limit", limit or 0)

        ctx.obj["config"] = config

    repo_path = repository or Path.cwd()
    if not isinstance(repo_path, Path):
        repo_path = Path(repo_path)

    ctx.obj["analyzer"] = RepoAnalyzer(
        path=repo_path,
        options=GitOptions(
            branch=branch,
            allow_dirty=allow_dirty,
            ignore_whitespace=ignore_whitespace,
            ignore_merges=ignore_merges,
        ),
        persistence=persist,
    )
    ctx.obj["data_selection"] = dict(
        aggregate_by=aggregate_by,
        identify_by=identify_by,
        sort_by=sort_by,
        aliases=aliases or {},
        exclude_users=exclude_users or [],
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        exclude_generated=exclude_generated,
    )
    ctx.obj["output"] = dict(img_location=img_location, output_file_paths=output_to)


@cli.command()
@click.pass_context
def summary(ctx: click.Context):
    """Generate very high level summary for the repository"""
    ra = ctx.obj.get("analyzer")
    _ = ra.summary(
        SummaryCmdOptions(
            **ctx.obj.get("data_selection"),
            **ctx.obj.get("output", {}),
        )
    )


@cli.command()
@click.pass_context
def revisions(ctx: click.Context):
    """List all revisions in the repository"""
    ra = ctx.obj.get("analyzer")
    _ = ra.revisions(
        RevisionsCmdOptions(**ctx.obj.get("data_selection"), **ctx.obj.get("output"))
    )


@cli.command
@click.option(
    "--report-type",
    "-t",
    type=click.Choice(choices=["user", "users", "file", "files"]),
    default="user",
)
@click.pass_context
def activity_report(
    ctx: click.Context,
    report_type: Literal["user", "users", "file", "files"],
):
    """Produces file or author report of activity at a particular git revision"""
    ra = ctx.obj.get("analyzer")

    options = ActivityReportCmdOptions(
        **ctx.obj.get("data_selection", {}), **ctx.obj.get("output", {})
    )
    if report_type.lower().startswith("file"):
        _ = ra.file_report(options)
    else:
        _ = ra.contributor_report(options)


@cli.command
@click.option("--revision", "-R", "revision", type=str, default=None)
@click.pass_context
def repo_blame(
    ctx: click.Context,
    revision: str,
):
    """Computes the per user blame for all files at a given revision"""
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = BlameCmdOptions(
        **ctx.obj.get("data_selection"), **ctx.obj.get("output", {})
    )
    data_key = "lines"
    _ = ra.blame(options, rev=revision, data_field=data_key)


@cli.command()
@click.pass_context
def cumulative_blame(ctx: click.Context):
    """Computes the cumulative blame of the repository over time. For every file in every revision,
    calculate the blame information.
    """
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = BlameCmdOptions(
        **ctx.obj.get("data_selection"), **ctx.obj.get("output", {})
    )
    _ = ra.cumulative_blame(options)


@cli.command()
@click.argument("identifier", type=str)
@click.pass_context
def punchcard(ctx: click.Context, identifier: str):
    """Computes commits for a given user by datetime"""
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = PunchcardCmdOptions(
        **ctx.obj.get("data_selection"),
        **ctx.obj.get("output", {}),
        identifier=identifier,
    )

    _ = ra.punchcard(options)


@cli.command
def serve():
    raise NotImplementedError()
