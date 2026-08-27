"""RepoAnalyzer: walk once, then run reports over the frames.

python examples/02_reports.py [repo-path]
"""

import rpo
from _common import repo_from_argv

repo = repo_from_argv()

# Walk options are fixed here and apply to every report below. This
# mirrors the Rust builder: RepoAnalyzer::open(path).with_*(...).
ra = rpo.RepoAnalyzer(repo)
print(ra, "\n")

print("== summary ==")
print(ra.summary(), "\n")

print("== contributors, by name ==")
print(ra.contributor_report(limit=5), "\n")

# Report-time options are keyword arguments. Grouping by email
# distinguishes people who commit under several display names.
print("== contributors, by email ==")
print(ra.contributor_report(identify_by="email", limit=5), "\n")

print("== busiest files ==")
print(ra.file_report(limit=5), "\n")

print("== lines surviving at HEAD ==")
print(ra.blame_report(limit=5), "\n")

# Attribute to whoever *applied* the change rather than who wrote it.
print("== by committer ==")
print(ra.contributor_report(aggregate_by="committer", limit=3), "\n")

print("== when commits land (day 1 = Monday) ==")
print(ra.punchcard().head(5))
