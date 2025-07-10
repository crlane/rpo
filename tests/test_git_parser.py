import pytest

from rpo.git_parser import GitParser


@pytest.fixture
def inc_blame_result():
    return """13188e5453ae23bee9dedcc1d1aae569b57ef633 3 3 1
author Cameron Lane
author-mail <858859+crlane@users.noreply.github.com>
author-time 1751819002
author-tz -0400
committer GitHub
committer-mail <noreply@github.com>
committer-time 1751819002
committer-tz -0400
summary Major refactor of core functionality (#3)
previous ab3a2aa01d5ec92fc12fd301fab6501fd3de13c6 README.md
filename README.md
a438f1f38b5134ce902b5451b76c6d9fb0951c16 173 174 8
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1751140988
author-tz -0400
committer Cameron Lane
committer-mail <lane.cameron@gmail.com>
committer-time 1751141614
committer-tz -0400
summary Publishing workflow
previous d8a8f9ff7290e80b6154eb5ca1ed23f10a6bb5b0 README.md
filename README.md
f52603d40fe846aed670d65a0fcf2a6788522dc8 133 134 1
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1750675678
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1750675678
committer-tz -0400
summary Readme fixup
previous 7fbbab62bee07c57801661cfb64a90b8ef21084e README.md
filename README.md
f52603d40fe846aed670d65a0fcf2a6788522dc8 136 137 1
previous 7fbbab62bee07c57801661cfb64a90b8ef21084e README.md
filename README.md
f52603d40fe846aed670d65a0fcf2a6788522dc8 152 153 1
previous 7fbbab62bee07c57801661cfb64a90b8ef21084e README.md
filename README.md
c43098e395f26e0accf50af0b44976c96b735159 137 138 15
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1750624593
author-tz -0400
committer Cameron Lane
committer-mail <lane.cameron@gmail.com>
committer-time 1750673010
committer-tz -0400
summary More work on duckdb, more efficient commit iteration, cli tests
previous d96ed9cdf8a26bacc4209e65943c2a98d096b334 README.md
filename README.md
c43098e395f26e0accf50af0b44976c96b735159 152 154 20
previous d96ed9cdf8a26bacc4209e65943c2a98d096b334 README.md
filename README.md
9c3047034e23ce4ffb521a0cae439e19daafecfb 21 22 13
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1750420432
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1750420432
committer-tz -0400
summary Updated readme for a5
previous 022730fb1de68949fc8b80cd829c96d983ad171b README.md
filename README.md
9c3047034e23ce4ffb521a0cae439e19daafecfb 46 47 10
previous 022730fb1de68949fc8b80cd829c96d983ad171b README.md
filename README.md
9c3047034e23ce4ffb521a0cae439e19daafecfb 61 62 1
previous 022730fb1de68949fc8b80cd829c96d983ad171b README.md
filename README.md
022730fb1de68949fc8b80cd829c96d983ad171b 129 135 2
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1750420223
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1750420310
committer-tz -0400
summary Fixes and Alpha 5
previous f2ec3638121c07998905f0d46d694d6e356b55bf README.md
filename README.md
73b0142631f5c7e7e14f56e0aaa1db22b186da98 82 89 1
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749766463
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749766463
committer-tz -0400
summary Fix README examples
previous 9de54d72d86a99a9c1923513884835e9aa2f50f4 README.md
filename README.md
73b0142631f5c7e7e14f56e0aaa1db22b186da98 102 109 1
previous 9de54d72d86a99a9c1923513884835e9aa2f50f4 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 19 20 2
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749732463
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749732463
committer-tz -0400
summary alpha3
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 34 35 12
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 54 60 2
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 56 63 1
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 68 75 3
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 78 85 3
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
9de54d72d86a99a9c1923513884835e9aa2f50f4 85 92 4
previous 59fd143a6dfb56fdbc7955a7f9c123dc390f34b7 README.md
filename README.md
5abdf420b473fabb49853aaf7cf10b1e1a1cd42b 5 6 2
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749651680
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749651680
committer-tz -0400
summary Readme caveat
previous cc01defb8a2a3e308ef3994198c317b1b7b37a0b README.md
filename README.md
5abdf420b473fabb49853aaf7cf10b1e1a1cd42b 91 117 1
previous cc01defb8a2a3e308ef3994198c317b1b7b37a0b README.md
filename README.md
afe101b1c2b8ff1eef128a2427d3e51de0466f64 41 18 2
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749602699
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749602699
committer-tz -0400
summary Readme update
previous c7378359b9c3f5c858f38ad63765d4ea4ac3be09 README.md
filename README.md
afe101b1c2b8ff1eef128a2427d3e51de0466f64 49 65 1
previous c7378359b9c3f5c858f38ad63765d4ea4ac3be09 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 3 4 1
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749592266
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749592266
committer-tz -0400
summary Preparing for initial alpha release
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 50 71 1
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 58 81 4
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 63 88 1
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 65 90 2
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 67 96 13
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 81 110 3
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 86 115 2
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 89 118 2
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
f8e4bba803fff46f1741659bdc5bd665dc4e8d83 97 126 1
previous eeb13871ae78d249cd7306b0ee9a3f1530531419 README.md
filename README.md
eeb13871ae78d249cd7306b0ee9a3f1530531419 12 11 1
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749518453
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749518453
committer-tz -0400
summary Fix formatting and remove unnecessary print debug
previous 451d793a908ffc4868ce65ee35ca04d2afb40f32 README.md
filename README.md
eeb13871ae78d249cd7306b0ee9a3f1530531419 45 66 1
previous 451d793a908ffc4868ce65ee35ca04d2afb40f32 README.md
filename README.md
451d793a908ffc4868ce65ee35ca04d2afb40f32 13 13 3
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749518234
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749518234
committer-tz -0400
summary Updated readme
previous 12a384f738a835cee8f454f47b9c4a6fe2f738ce README.md
filename README.md
451d793a908ffc4868ce65ee35ca04d2afb40f32 35 16 2
previous 12a384f738a835cee8f454f47b9c4a6fe2f738ce README.md
filename README.md
451d793a908ffc4868ce65ee35ca04d2afb40f32 37 57 3
previous 12a384f738a835cee8f454f47b9c4a6fe2f738ce README.md
filename README.md
451d793a908ffc4868ce65ee35ca04d2afb40f32 42 64 1
previous 12a384f738a835cee8f454f47b9c4a6fe2f738ce README.md
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 1 1 2
author Cameron Lane
author-mail <crlane@adamanteus.com>
author-time 1749518060
author-tz -0400
committer Cameron Lane
committer-mail <crlane@adamanteus.com>
committer-time 1749518060
committer-tz -0400
summary initial commit
boundary
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 4 5 1
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 9 8 3
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 12 12 1
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 15 67 4
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 20 72 3
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 24 78 3
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 27 113 2
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 32 120 6
filename README.md
12a384f738a835cee8f454f47b9c4a6fe2f738ce 39 127 7
filename README.md
"""


def test_parse_blame_result(inc_blame_result):
    gp = GitParser()
    result = list(gp.parse_blame_result(inc_blame_result, "a" * 40, "test_path.py"))
    assert len(result) == 50
    assert result[0]["commit_sha"] == "13188e5453ae23bee9dedcc1d1aae569b57ef633"
    assert result[0]["num_lines"] == 1
    assert result[-1]["commit_sha"] == "12a384f738a835cee8f454f47b9c4a6fe2f738ce"
    assert result[-1]["num_lines"] == 7
