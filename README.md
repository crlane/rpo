# RPO: Repository Participation Observer

A command line tool and Python library to help you analyze and visualized Git repositories. Ever wondered who has most contributions? How participation has changed over time? What are the hotspots in your code that change frequently? Who has the highest bus factor? `rpo` can help.

> NOTE: This is alpha software under active development. There will be breaking changes.

## Usage

### CLI

```bash
Usage: rpo [OPTIONS] COMMAND [ARGS]...

Options:
  -g, --glob TEXT            File path glob patterns to INCLUDE. If specified,
                             matching paths will be the only files included in
                             aggregation.            If neither --glob nor
                             --xglob are specified, all files will be included
                             in aggregation. Paths are relative to root of
                             repository.
  -xg, --xglob TEXT          File path glob patterns to EXCLUDE. If specified,
                             matching paths will be filtered before
                             aggregation.            If neither --glob nor
                             --xglob are specified, all files will be included
                             in aggregation. Paths are relative to root of
                             repository.
  -A, --aggregate-by TEXT    Controls the field used to aggregate data
  -I, --identify-by TEXT     Controls the field used to identify auhors.
  -S, --sort-by TEXT         Controls the field used to sort output
  -a, --alias-file FILENAME  Not currently used. A JSON file that maps a
                             contributor name to one or more aliases.
                             Useful in cases where authors have used multiple
                             email addresses, names, or spellings to create
                             commits.
  -o, --output TEXT          Path of the output file; format is determined by
                             the filename extension.
  -r, --repository PATH
  -b, --branch TEXT
  --allow-dirty              Proceed with analyis even if repository has
                             uncommitted changes
  --help                     Show this message and exit.

Commands:
  activity-report  Simple commit report aggregated by author or committer
  repo-blame       Computes the per contributor blame for all files at a...
  revisions        List all revisions in the repository
  summary          Generate very high level summary for the repository
  ```

### Library

```bash
pip install rpo
```

```python
from rpo import Project, Repository


```
## Examples

> NOTE: depending on your shell, you may or may not need to escape the splat character in the glob patterns used below.

### Git Blame for all Files in a Repo at a Given Revision, Identify Authors by Email
```
$ rpo -r ../my-local-repo -I email repo-blame -R HEAD
```


### Author Activity Report, Including Only Files that Match a Pattern
```
$ rpo -r ../my-local-repo -g tests/\* activity-report
```

### Author Activity Report, Excluding Files that Match a Pattern
```
$ rpo -r ../my-local-repo -xg tests/\* activity-report
```

### File Activity Report, Excluding Files that Match a Pattern
```
$ rpo -r ../my-local-repo -xg tests/\* activity-report --files-report
```


## Features
- [ ] Automatically generate aliases that refer to the same person
- [x] Support analyzing by glob
- [x] Support excluding by glob
- [x] Produce blame charts
- [x] Optionally ignore merge commits
- [x] Optionally ignore whitespace
- [ ] Identify major refactorings
- [ ] Fast execution, even on giant repositories


## Performance

The goal is for the library to work even on the largest libraries. In general, the performance is proportional to the number of authors, commits, and files being considered in the aggregations.

The authors regularly [test](./tests/integration/test_cpython_repository.py) using the [cpython repository](https://github.com/python/cpython), which contains over 1,000,000 objects. That takes a while.

> TODO: Performance graphs

## Similar Projects and Inspiration

Thanks to [GitPandas](https://github.com/wdm0006/git-pandas) for inspiration.

