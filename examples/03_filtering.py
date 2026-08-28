"""Narrowing what the walk sees.

Filters are applied by the engine at walk time, so they affect every
report consistently — and cost nothing extra, since excluded paths never
enter the frames.

    python examples/03_filtering.py [repo-path]
"""

import rpo
from _common import repo_from_argv

repo = repo_from_argv()

everything = rpo.RepoAnalyzer(repo)
print(f"unfiltered:            {everything.file_changes.height:5d} file changes")

# Exclusions win over inclusions. Both are repeatable.
no_docs = rpo.RepoAnalyzer(repo, exclude_globs=["docs/**", "**/*.md"])
print(f"without docs/markdown: {no_docs.file_changes.height:5d}")

src_only = rpo.RepoAnalyzer(repo, include_globs=["python/**", "src/**"])
print(f"source trees only:     {src_only.file_changes.height:5d}")

# Globs are globset patterns matched against the full repo-relative path.
# Separators are NOT special: "*.py" matches "python/rpo/analyzer.py".
py_only = rpo.RepoAnalyzer(repo, include_globs=["*.py"])
print(f"every .py at any depth:{py_only.file_changes.height:5d}")

print("\n-- activity options --")
print("(identical counts just mean this repo has no merges or bot commits)")
# Merge commits double-count work, so they are excluded by default.
with_merges = rpo.RepoAnalyzer(repo, ignore_merges=False)
print(f"commits, merges excluded (default): {everything.commits.height}")
print(f"commits, merges included:           {with_merges.commits.height}")

# Drop GitHub [bot] identities, which otherwise dominate some repos.
no_bots = rpo.RepoAnalyzer(repo, ignore_bots=True)
print(f"commits, bots dropped:              {no_bots.commits.height}")

# Follow only the first parent — a release-branch view of history.
first_parent = rpo.RepoAnalyzer(repo, first_parent_only=True)
print(f"commits, first-parent only:         {first_parent.commits.height}")

print("\n-- a malformed glob fails loudly --")
try:
    rpo.RepoAnalyzer(repo, exclude_globs=["["])
except rpo.InvalidGlobError as e:
    print(f"InvalidGlobError: {e}")

try:
    rpo.RepoAnalyzer("/definitely/not/a/repository")
except rpo.NotARepositoryError as e:
    print(f"NotARepositoryError: {e}")
