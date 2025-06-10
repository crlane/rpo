# RPO: Repository Participation Observer

A command line tool and Python library to help you analyze and visualized Git repositories. Ever wondered who has most contributions? How participation has changed over time? What are the hotspots in your code? Who has the highest bus factor? `rpo` can help.

A note on analyzing code repositories: Attempting to quantify developer productivity by lines of code (or git commits) is generally a bad idea. `rpo` is designed to help you uncover how your code's contribution model has changed over time, and how you can build a more efficient and sustainable software operation. The tools here _might_ tell you something about your development team - but it's even more likely that they'll tell you something about your *management*. Do you have high turnover and/or burnout problems? Are people committing way outside their normal work hours? How are you doing at documentation and knowledge transfer?

All that to say, while I hope this tool will be useful, it is not a substitute for thinking.

## Usage

### CLI
```bash
rpo analyze -g
```

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
