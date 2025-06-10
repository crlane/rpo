# RPO: Repository Participation Observer

A command line tool and Python library to help you analyze and visualized Git repositories. Ever wondered who has most contributions? How participation has changed over time? What are the hotspots in your code? Who has the highest bus factor? `rpo` can help.

A note on analyzing code repositories: Attempting to quantify developer productivity by lines of code (or git commits) is generally a bad idea. `rpo` is designed to help you uncover how your code's contribution model has changed over time, and how you can build a more efficient and sustainable software operation. The tools here _might_ tell you something about your development team - but it's even more likely that they'll tell you something about your *management*. Do you have high turnover and/or burnout problems? Are people committing way outside their normal work hours? How are you doing at documentation and knowledge transfer?

All that to say, while I hope this tool will be useful, it is not a substitute for thinking.

## Usage

### CLI
```bash
Usage: rpo [OPTIONS] COMMAND [ARGS]...

Options:
  -g, --glob TEXT            File path glob patterns to INCLUDE. If specified,
                             matching paths will be the only files included in
                             aggregation. If neither --glob nor --xglob are
                             specified, all files will be included in
                             aggregation. Paths are relative to root of
                             repository.
  -xg, --xglob TEXT          File path glob patterns to EXCLUDE. If specified,
                             matching paths will be filtered before
                             aggregation. If neither --glob nor --xglob are
                             specified, all files will be included in
                             aggregation. Paths are relative to root of
                             repository.
  -A, --aggregate-by TEXT
  -I, --identify-by TEXT
  -S, --sort-by TEXT
  -a, --alias-file FILENAME  A JSON file that maps a contributor name to one
                             or more aliases. Useful in cases where authors
                             have used multiple email addresses, names, or
                             spellings to create commits.
  -r, --repository PATH
  -b, --branch TEXT
  --help                     Show this message and exit.

Commands:
  activity-report  Simple commit report aggregated by author or committer
  repo-blame       Computes the per contributor blame for all files at a...
  revisions        List all revisions in the repository
  summary```

### Library

```bash
pip install repostats
```

```python
from repostats import Project, Repository


```
## Features
- [ ] Automatically generate aliases that refer to the same person
- [ ] Support analyzing by glob
- [ ] Produce blame charts,
- [ ] Ignore merge commits
- [ ] Identify major refactorings
- [ ] Fast execution, even on giant repositories


## Performance

The goal is for the library to work even on the largest libraries. In general, the performance is proportial to the number of authors, commits, and files being considered in the aggregations.

The authors regularly [test](./tests/integration/test_cpython_repository.py) using the [cpython repository](https://github.com/python/cpython), which contains over 1,000,000 objects. That takes a while.

> TODO: Performance graphs

## Similar Projects and Inspiration

Thanks to [GitPandas](https://github.com/wdm0006/git-pandas).
