"""Shared helper: pick the repository an example should analyze."""

import sys
from pathlib import Path


def repo_from_argv(default: str | None = None) -> str:
    """The path given on the command line, or a sensible default.

    Examples run against this checkout when no argument is given, so
    they work immediately after cloning.
    """
    if len(sys.argv) > 1:
        return sys.argv[1]
    if default:
        return default
    return str(Path(__file__).resolve().parent.parent)
