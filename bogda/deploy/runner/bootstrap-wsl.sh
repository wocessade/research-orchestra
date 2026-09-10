#!/bin/sh
# WSL2 Ubuntu bootstrap for the stand-in research runner.
# Does not copy host skills, does not talk to 3100, does not use pi-service.
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "run this inside WSL2 Ubuntu, not Windows native" >&2
    exit 1
fi

if grep -qi microsoft /proc/version 2>/dev/null; then
    :
else
    echo "this script expects WSL2; bare Linux needs an owner-approved contract change" >&2
    exit 1
fi

case "$(pwd -P)" in
    /mnt/c/*|/mnt/d/*|/mnt/e/*)
        echo "do not use /mnt/c as the worker home; clone onto the WSL ext4 disk" >&2
        exit 1
        ;;
esac

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates cifs-utils python3 python3-venv build-essential

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1091
    . "$HOME/.local/bin/env" 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
fi

mkdir -p "$HOME/.config/bogda" "$HOME/bogda-work"
chmod 700 "$HOME/.config/bogda" "$HOME/bogda-work"

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$HOME/.config/bogda/runner.env" ]; then
    sed "s|/home/REPLACE|$HOME|g" "$HERE/runner.env.example" > "$HOME/.config/bogda/runner.env"
    chmod 600 "$HOME/.config/bogda/runner.env"
    echo "wrote $HOME/.config/bogda/runner.env (empty HMAC, fill locally)"
else
    echo "keeping existing $HOME/.config/bogda/runner.env"
fi

if [ ! -f "$HOME/.config/bogda/nas.cred" ]; then
    cp "$HERE/nas.cred.example" "$HOME/.config/bogda/nas.cred"
    chmod 600 "$HOME/.config/bogda/nas.cred"
    echo "wrote $HOME/.config/bogda/nas.cred (put Samba password locally, chmod 600)"
fi

echo "WSL packages and config stubs ready."
echo "next: fill nas.cred and runner.env, mount-nas.sh, then start-worker.sh"
echo "do not paste HMAC / Prefect auth / Samba password into chat"
