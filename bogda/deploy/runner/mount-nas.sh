#!/bin/sh
# Mount the RK3528 Samba NAS at /mnt/nas so console and worker share one tree.
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

NAS_UNC=${NAS_UNC:-//rk3528.tail6d8b09.ts.net/nas}
NAS_MOUNT=${NAS_MOUNT:-/mnt/nas}
NAS_CRED_FILE=${NAS_CRED_FILE:-$HOME/.config/bogda/nas.cred}

if [ ! -f "$NAS_CRED_FILE" ]; then
    echo "missing $NAS_CRED_FILE" >&2
    exit 1
fi
if grep -q '^password=$' "$NAS_CRED_FILE"; then
    echo "put the Samba password into $NAS_CRED_FILE first" >&2
    exit 1
fi

sudo mkdir -p "$NAS_MOUNT"
if findmnt -n "$NAS_MOUNT" >/dev/null 2>&1; then
    echo "$NAS_MOUNT already mounted"
else
    sudo mount -t cifs "$NAS_UNC" "$NAS_MOUNT" \
        -o "credentials=$NAS_CRED_FILE,uid=$(id -u),gid=$(id -g),file_mode=0750,dir_mode=0750,vers=3.0,nofail"
fi

for path in \
    "$NAS_MOUNT/.bogda/inbox" \
    "$NAS_MOUNT/.bogda/runner" \
    "$NAS_MOUNT/.bogda/runner/artifacts"
do
    if [ ! -d "$path" ]; then
        echo "missing $path — run prepare_runner_share.sh on the box first" >&2
        exit 1
    fi
done

echo "NAS ready at $NAS_MOUNT"
