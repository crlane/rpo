#!/usr/bin/env bash
set -euo pipefail

get_last_directory() {
    local path="$1"
    basename "$(dirname "$path")"
}
REPO=${REPO:-../requests}
IDENTIFIER=${IDENTIFIER:-me@kennethreitz.com}
PLOT_DIR=${PLOT_DIR:-$(pwd)/img/$(basename "$REPO")}
BY=${BY:-email}

echo "**** SUMMARY ****"
uv run rpo -r "$REPO" summary
printf "\n\n\n"

echo "**** REVISIONS ****"
uv run rpo -r "$REPO" revisions
printf "\n\n\n"
#
echo "**** USER ACTIVITY ****"
uv run rpo -r "$REPO" -I "$BY" activity-report -t user
printf "\n\n\n"
#
echo "**** FILE ACTIVITY ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated-files activity-report -t file
printf "\n\n\n"

echo "**** BLAME ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated-files --plot "$PLOT_DIR" repo-blame
printf "\n\n\n"

echo "**** CUMULATIVE BLAME ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated-files --plot "$PLOT_DIR" cumulative-blame
printf "\n\n\n"

echo "**** PUNCHARD ****"

uv run rpo -r ../git-pandas -I email --exclude-generated-files --plot "$PLOT_DIR" punchcard "$IDENTIFIER"
printf "\n\n\n"
