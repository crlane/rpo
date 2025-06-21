#!/usr/bin/env bash
set -euox pipefail

get_last_directory() {
    local path="$1"
    basename "$(dirname "$path")"
}
REPO=${REPO:-../requests}
IDENTIFIER=${IDENTIFIER:-me@kennethreitz.com}
PLOT_DIR=${PLOT_DIR:-$(pwd)/img/$(basename "$REPO")}
BY=${BY:-email}

echo "**** SUMMARY ****"
uv run rpo -r "$REPO" -o - summary
printf "\n\n\n"

echo "**** REVISIONS ****"
uv run rpo -r "$REPO" -o - revisions
printf "\n\n\n"
#
echo "**** USER ACTIVITY ****"
uv run rpo -r "$REPO" -I "$BY" -o - activity-report -t user
printf "\n\n\n"
#
echo "**** FILE ACTIVITY ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - activity-report -t file
printf "\n\n\n"

echo "**** BLAME ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - --plot "$PLOT_DIR" repo-blame
printf "\n\n\n"

echo "**** BLAME SAVE JSON ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - -o "$PLOT_DIR/blame.json" repo-blame
printf "\n\n\n"

echo "**** BLAME SAVE CSV ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - -o "$PLOT_DIR/blame.csv" repo-blame
printf "\n\n\n"

echo "**** BLAME SAVE BOTH ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - -o "$PLOT_DIR/blame2.json" -o "$PLOT_DIR/blame2.csv" repo-blame
printf "\n\n\n"

echo "**** CUMULATIVE BLAME ****"
uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - --plot "$PLOT_DIR" cumulative-blame
printf "\n\n\n"

echo "**** PUNCHARD ****"

uv run rpo -r "$REPO" -I "$BY" --exclude-generated -o - --plot "$PLOT_DIR" punchcard "$IDENTIFIER"
printf "\n\n\n"
