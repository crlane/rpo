from pathlib import Path

import pytest
from click.testing import CliRunner

from rpo.main import cli


@pytest.fixture
def runner():
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0, "CLI command failed"


@pytest.mark.slow
@pytest.mark.parametrize("identify_by", ["name", "email"])
@pytest.mark.parametrize("subcommand", ["repo-blame", "cumulative-blame", "punchcard"])
@pytest.mark.parametrize(
    "plot_path", ["img", "img/some_blame_file.png"], ids=("directory", "filename")
)
def test_plottable_subcommands(
    plot_path, subcommand, identify_by, runner, tmp_repo, actors
):
    args = [
        "-r",
        tmp_repo.working_dir,
        "-I",
        identify_by,
        "--plot",
        plot_path,
        subcommand,
    ]
    if subcommand == "punchcard":
        args.append(getattr(actors[-1], identify_by))
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, (
        f"CLI command failed, Output: {result.output}\nExc: {result.exc_info}"
    )
    p = Path(plot_path)
    assert p.exists(), "Plot path does not exist"
    if p.is_dir():
        assert len(list(p.glob("*.png"))) == 1, "Image file DNE"
