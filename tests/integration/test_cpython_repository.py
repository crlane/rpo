import pytest
from git import Repo


@pytest.mark.slow
def test_cpython(cpython_repo: Repo):
    assert not cpython_repo.bare
