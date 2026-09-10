#!/bin/sh
# Print Prefect IDs to copy onto the box env. Does not print HMAC or auth.
set -eu

ENV_FILE="${BOGDA_RUNNER_ENV:-$HOME/.config/bogda/runner.env}"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    . "$ENV_FILE"
    set +a
fi

export PATH="$HOME/.local/bin:$PATH"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$HERE/../../.." && pwd)
cd "$REPO/bogda"

echo "# paste these onto the box 3101 env. do not paste HMAC."
echo "# exact IDs are read from the dorm-x86 pool only; no auth or HMAC is printed."
uv run --python 3.11 python - <<'PY'
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterName


POOL_NAME = "dorm-x86"


with get_client(sync_client=True) as client:
    pool_filter = WorkPoolFilter(name=WorkPoolFilterName(any_=[POOL_NAME]))
    pools = client.read_work_pools(work_pool_filter=pool_filter)
    if len(pools) != 1:
        raise SystemExit(f"expected exactly one {POOL_NAME} work pool, found {len(pools)}")
    pool = pools[0]
    queues = client.read_work_queues(work_pool_name=POOL_NAME, limit=200)
    deployments = client.read_deployments(work_pool_filter=pool_filter, limit=200)

    print(f"BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES={pool.name}")
    print(f"# pool_id={pool.id}")
    print("BOGDA_CONSOLE_ALLOWED_QUEUE_IDS=" + ",".join(str(queue.id) for queue in queues))
    print(
        "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS="
        + ",".join(str(deployment.id) for deployment in deployments)
    )
PY
echo
echo "fill BOGDA_CONSOLE_ALLOWED_QUEUE_IDS and BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS with exact ids (no *)"
echo "leave 3101 on real-readonly until those env values exist on the box"
