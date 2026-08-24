import json
import logging
from os import PathLike, getenv
from pathlib import Path
from typing import Literal

import click
from click_aliases import ClickAliasedGroup
from pydanclick import from_pydantic

from .analyzer import RepoAnalyzer
from .models import (
    ActivityReportCmdOptions,
    BlameCmdOptions,
    DataSelectionOptions,
    FileSaveOptions,
    GitOptions,
    OutputOptions,
    PunchcardCmdOptions,
    RevisionsCmdOptions,
    SummaryCmdOptions,
)

logging.basicConfig(
    level=getenv("LOG_LEVEL", logging.INFO),
    format="[%(asctime)s] %(levelname)s: %(name)s.%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S.%s",
)
logger = logging.getLogger(__name__)


def file_options(func):
    return from_pydantic(
        "file_output", FileSaveOptions, shorten={}, rename={"JSON": "json"}
    )(func)


def data_options(func):
    return from_pydantic(
        "data_options",
        DataSelectionOptions,
        rename={"include_globs": "glob", "exclude_globs": "xglob"},
        exclude=["aliases", "exclude_users", "sort_descending"],
        shorten={
            "identify_by": "-I",
            "aggregate_by": "-A",
            "sort_by": "-S",
            "include_globs": "-g",
            "exclude_globs": "-xg",
        },
    )(func)


def plot_options(func):
    return from_pydantic("file_output", OutputOptions, rename={})(func)


@click.group("rpo", cls=ClickAliasedGroup)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(readable=True, dir_okay=False),
    help="The location of the json formatted config file to use. Defaults to a hidden config.json file in the current working directory. If it exists, then options in the config file take precedence over command line flags.",
)
@from_pydantic("options", GitOptions, shorten={"path": "-p", "branch": "-b"})
@click.pass_context
def cli(
    ctx: click.Context,
    options: GitOptions,
    config_file: PathLike[str] | None = None,
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
        for k, new in config.items():
            if k in options:
                old = getattr(options, k)
                setattr(options, k, new)
                logger.info(f"Config file overidden option {k}: {old}->{new}")
        ctx.obj["config"] = config

    ctx.obj["analyzer"] = RepoAnalyzer(
        options=options,
        in_memory=not options.persist_data,
    )


@cli.command()
@data_options
@file_options
@click.pass_context
def summary(
    ctx: click.Context, data_options: DataSelectionOptions, file_output: FileSaveOptions
):
    """Generate very high level summary for the repository"""
    ra = ctx.obj.get("analyzer")
    _ = ra.summary(
        SummaryCmdOptions(**data_options.model_dump(), **file_output.model_dump())
    )


@cli.command()
@data_options
@file_options
@click.pass_context
def revisions(
    ctx: click.Context, data_options: DataSelectionOptions, file_output: FileSaveOptions
):
    """List all revisions in the repository"""
    ra = ctx.obj.get("analyzer")
    _ = ra.revisions(
        RevisionsCmdOptions(**data_options.model_dump(), **file_output.model_dump())
    )


@cli.command(aliases=["activity"])
@click.option(
    "--report-type",
    "-t",
    type=click.Choice(choices=["user", "users", "file", "files"]),
    default="user",
)
@data_options
@plot_options
@click.pass_context
def activity_report(
    ctx: click.Context,
    data_options: DataSelectionOptions,
    file_output: OutputOptions,
    report_type: Literal["user", "users", "file", "files"],
):
    """Produces file or author report of activity at a particular git revision"""
    ra = ctx.obj.get("analyzer")

    options = ActivityReportCmdOptions(
        **file_output.model_dump(), **data_options.model_dump()
    )  #
    if report_type.lower().startswith("file"):
        _ = ra.file_report(options)
    else:
        _ = ra.contributor_report(options)


#
#
@cli.command
@data_options
@plot_options
@click.option("--revision", "-R", "revision", type=str, default=None)
@click.pass_context
def blame(
    ctx: click.Context,
    data_options: DataSelectionOptions,
    file_output: OutputOptions,
    revision: str,
):
    """Computes the per user blame for all files at a given revision"""
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = BlameCmdOptions(
        **file_output.model_dump(), **data_options.model_dump()
    )  #
    data_key = "lines"
    _ = ra.blame(options, rev=revision, data_field=data_key)


#
#
@cli.command(aliases=["cblame"])
@data_options
@plot_options
@click.pass_context
def cumulative_blame(
    ctx: click.Context, data_options: DataSelectionOptions, file_output: FileSaveOptions
):
    """Computes the cumulative blame of the repository over time. For every file in every revision,
    calculate the blame information.
    """
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = BlameCmdOptions(
        **file_output.model_dump(), **data_options.model_dump()
    )  #
    _ = ra.cumulative_blame(options)


@cli.command()
@data_options
@plot_options
@click.argument("identifier", type=str)
@click.pass_context
def punchcard(
    ctx: click.Context,
    identifier: str,
    data_options: DataSelectionOptions,
    file_output: FileSaveOptions,
):
    """Computes commits for a given user by datetime"""
    ra: RepoAnalyzer = ctx.obj.get("analyzer")
    options = PunchcardCmdOptions(
        identifier=identifier, **file_output.model_dump(), **data_options.model_dump()
    )  #
    _ = ra.punchcard(options)
