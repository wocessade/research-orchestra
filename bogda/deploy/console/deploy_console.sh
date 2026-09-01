#!/usr/bin/env bash
# Deploy Bogda Console to RK3528. Does not run Prefect install.sh. Does not touch 3100.
# Usage: ORCHESTRA_SSH_HOST=100.78.158.80 bash bogda/deploy/console/deploy_console.sh
set -eu

SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
SSH_HOST="${ORCHESTRA_SSH_HOST:-100.78.158.80}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
STAGE_LOCAL="${TMPDIR:-/tmp}/bogda-console-stage-$$"
REMOTE_STAGE="/tmp/bogda-console-stage-$$"

if [ ! -f "$ROOT/bogda-console/frontend/dist/index.html" ]; then
    echo "frontend/dist missing. From bogda-console run: npm run build" >&2
    exit 1
fi
if [ ! -f "$ROOT/bogda-console/fixtures/normal-active.json" ]; then
    echo "bogda-console/fixtures missing. real-readonly still loads MockPowerAdapter fixtures." >&2
    exit 1
fi

mkdir -p "$STAGE_LOCAL"
cp -a "$ROOT/bogda-console/src" "$STAGE_LOCAL/src"
cp -a "$ROOT/bogda-console/pyproject.toml" "$STAGE_LOCAL/pyproject.toml"
cp -a "$ROOT/bogda-console/frontend/dist" "$STAGE_LOCAL/dist"
cp -a "$ROOT/bogda-console/fixtures" "$STAGE_LOCAL/fixtures"
cp -a "$ROOT/bogda/deploy/console/bogda-console.service" "$STAGE_LOCAL/"
cp -a "$ROOT/bogda/deploy/console/maintain.sh" "$STAGE_LOCAL/"
cp -a "$ROOT/bogda/deploy/console/dsh-maintain.md" "$STAGE_LOCAL/"
cp -a "$ROOT/bogda/deploy/console/console.env.example" "$STAGE_LOCAL/"
cp -a "$ROOT/bogda/deploy/console/remote-install.sh" "$STAGE_LOCAL/"

scp -q -r "$STAGE_LOCAL" "$SSH_USER@$SSH_HOST:$REMOTE_STAGE"
ssh "$SSH_USER@$SSH_HOST" "sudo bash $REMOTE_STAGE/remote-install.sh $REMOTE_STAGE"
rm -rf "$STAGE_LOCAL"
echo "deployed. MagicDNS: http://rk3528.tail6d8b09.ts.net:3101/  (loopback on box: http://127.0.0.1:3101/; tailnet IP :3101 is serve 404)"
