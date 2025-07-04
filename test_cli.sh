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
uv run rpo -p "$REPO" summary
printf "\n\n\n"

echo "**** REVISIONS ****"
uv run rpo -p "$REPO" revisions
printf "\n\n\n"
#
echo "**** USER ACTIVITY ****"
uv run rpo -p "$REPO" activity -t user -I "$BY"
printf "\n\n\n"
#
echo "**** FILE ACTIVITY ****"
uv run rpo -p "$REPO" activity -t file -I "$BY"
printf "\n\n\n"

echo "**** BLAME ****"
uv run rpo -p "$REPO" blame -I "$BY" --visualize --img-location "$PLOT_DIR"
printf "\n\n\n"

echo "**** BLAME SAVE JSON ****"
uv run rpo -p "$REPO" blame -I "$BY" --json --no-visualize

echo "**** BLAME SAVE CSV ****"
uv run rpo -p "$REPO" blame -I "$BY" --csv --no-visualize
printf "\n\n\n"

echo "**** BLAME SAVE BOTH ****"
uv run rpo -p "$REPO" blame -I "$BY" --csv --json --no-visualize
printf "\n\n\n"

echo "**** CUMULATIVE BLAME ****"
uv run rpo -p "$REPO" cblame -I "$BY" --visualize --img-location "$PLOT_DIR"
printf "\n\n\n"

echo "**** PUNCHARD ****"

uv run rpo -p "$REPO" punchcard "$IDENTIFIER" -I "$BY" --visualize --img-location "$PLOT_DIR"
printf "\n\n\n"
