#!/bin/sh
# Start the research process worker. Pool name is the software contract.
# This host is a stand-in laptop: no Wake Bridge, concurrency stays 1.
set -eu

ENV_FILE="${BOGDA_RUNNER_ENV:-$HOME/.config/bogda/runner.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "missing $ENV_FILE" >&2
    exit 1
fi
# shellcheck disable=SC1090
set -a
. "$ENV_FILE"
set +a

POOL=${BOGDA_RESEARCH_POOL:-}
LIMIT=${BOGDA_WORKER_LIMIT:-}

if [ "$POOL" != "dorm-x86" ]; then
    echo "refusing pool '$POOL' (research worker must use dorm-x86, never pi-service)" >&2
    exit 1
fi
if [ "$LIMIT" != "1" ]; then
    echo "refusing BOGDA_WORKER_LIMIT='$LIMIT' (must stay 1)" >&2
    exit 1
fi
if [ -z "${PREFECT_API_URL:-}" ]; then
    echo "PREFECT_API_URL is empty" >&2
    exit 1
fi
if [ -z "${BOGDA_STORE_API_URL:-}" ]; then
    echo "BOGDA_STORE_API_URL is empty (console-owned budget/approval stores)" >&2
    exit 1
fi
if [ -z "${BOGDA_APPROVAL_HMAC_KEY:-}" ]; then
    echo "BOGDA_APPROVAL_HMAC_KEY is empty; generate it on this machine or the box" >&2
    exit 1
fi
for path in "${BOGDA_ARTIFACT_ROOT:?}"
do
    if [ ! -d "$path" ]; then
        echo "shared path missing: $path (mount NAS first)" >&2
        exit 1
    fi
done

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$HERE/../../.." && pwd)

WORKDIR=${BOGDA_RUNNER_WORK:-$HOME/bogda-work}
case "$WORKDIR" in
    /mnt/c/*|/mnt/d/*|/mnt/e/*)
        echo "BOGDA_RUNNER_WORK must be on the WSL disk, not /mnt/c" >&2
        exit 1
        ;;
esac
mkdir -p "$WORKDIR"
cd "$WORKDIR"

if [ ! -f "$REPO/bogda/pyproject.toml" ]; then
    echo "cannot find bogda/pyproject.toml from $HERE" >&2
    exit 1
fi

export PATH="$HOME/.local/bin:$PATH"
cd "$REPO/bogda"
echo "starting process worker pool=$POOL limit=$LIMIT api=$PREFECT_API_URL"
exec uv run --python 3.11 prefect worker start \
    --pool "$POOL" \
    --type process \
    --limit "$LIMIT" \
    --create-pool-if-not-found
