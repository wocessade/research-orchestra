#!/bin/sh
# Create NAS dirs that 3101 and a future runner share. No secrets. No funnel.
# Usage on RK3528: sudo bash bogda/deploy/shared/prepare_runner_share.sh
set -eu

if [ "$(findmnt -no FSTYPE /mnt/nas)" != "ext4" ]; then
    echo "/mnt/nas must be an ext4 mount" >&2
    exit 1
fi

if ! getent passwd bogda >/dev/null 2>&1; then
    echo "bogda user missing" >&2
    exit 1
fi

install -d -m 0750 -o bogda -g bogda \
    /mnt/nas/.bogda/inbox \
    /mnt/nas/.bogda/runner \
    /mnt/nas/.bogda/runner/artifacts

echo "prepared /mnt/nas/.bogda/inbox and /mnt/nas/.bogda/runner/artifacts"
