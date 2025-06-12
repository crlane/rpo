#!/usr/bin/env bash
set -euo pipefail

REPO=../git-pandas
BY=email

echo "**** SUMMARY ****"
uv run rpo -r $REPO summary
printf "\n\n\n"

echo "**** REVISIONS ****"
uv run rpo -r $REPO revisions
printf "\n\n\n"
#
echo "**** USER ACTIVITY ****"
uv run rpo -r $REPO -I $BY activity-report -t user
printf "\n\n\n"
#
echo "**** FILE ACTIVITY ****"
uv run rpo -r $REPO -I $BY --exclude-generated-files activity-report -t file
printf "\n\n\n"

echo "**** BLAME ****"
uv run rpo -r $REPO -I $BY --exclude-generated-files repo-blame
printf "\n\n\n"

echo "**** CUMULATIVE BLAME ****"
uv run rpo -r $REPO -I $BY --exclude-generated-files repo-blame
printf "\n\n\n"
