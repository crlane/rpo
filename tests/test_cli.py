import multiprocessing
from pathlib import Path
from traceback import format_exception

import pytest
from click.testing import CliRunner

from rpo.main import cli


@pytest.fixture
def runner():
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


def test_top_level_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0, "CLI command failed"


@pytest.mark.parametrize(
    "subcommand",
    [
        "summary",
        "revisions",
        "blame",
        "cumulative-blame",
    ],
)
def test_subcommand_help(runner, subcommand):
    result = runner.invoke(cli, [subcommand, "--help"])
    assert result.exit_code == 0, "CLI command failed"


@pytest.mark.slow
@pytest.mark.parametrize("identify_by", ["name", "email"])
@pytest.mark.parametrize(
    "persistence", ["--persist-data", "--no-persist-data"], ids=("persist", "inmemory")
)
@pytest.mark.parametrize("subcommand", ["blame", "cblame", "punchcard"])
def test_plottable_subcommands(
    subcommand, persistence, identify_by, runner, tmp_repo, actors
):
    args = [
        "-p",
        tmp_repo.working_dir,
        persistence,
        subcommand,
        "-I",
        identify_by,
        "--visualize",
        "--img-location",
        "./img",
    ]
    if subcommand == "punchcard":
        args.append(getattr(actors[-1], identify_by))
    # NOTE: https://github.com/pytest-dev/pytest/issues/11174 things get hung on github actions if this isn't set.
    multiprocessing.set_start_method("spawn", force=True)

    result = runner.invoke(cli, args)
    assert result.exit_code == 0, (
        f"CLI command failed, Output: {result.output}\nExc: {format_exception(*result.exc_info)}"
    )
    p = Path("./img")
    assert p.exists(), "Plot path does not exist"
    if p.is_dir():
        assert len(list(p.glob("*.png"))) == 1, "Image file DNE"
