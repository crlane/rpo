# see man git-log
AUTHOR_EMAIL_MAILMAP = aname = "%aE"
AUTHOR_NAME_MAILMAP = amail = "%aN"
AUTHOR_ISOTIME = atime = "%aI"
COMMITTER_EMAIL_MAILMAP = cname = "%cE"
COMMITTER_NAME_MAILMAP = cmail = "%cN"
COMMITTER_ISOTIME = ctime = "%cI"

SEPARATOR = "|"

GITLOG_FORMAT = SEPARATOR.join(
    ("%m", "%H", aname, amail, atime, cmail, cname, ctime, "%m")
)
# repo.git.log(repo.head, summary=True, numstat=True, format=")
