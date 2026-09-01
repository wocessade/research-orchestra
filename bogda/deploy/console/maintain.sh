#!/bin/sh
# Box-side console maintenance. dsh may only call this script.
# Allowed verbs: status | logs | restart | health
# Does not print /etc/bogda/console.env or bogda.env.
# Does not rebuild frontend, fetch source, or change profile.

set -eu

unit="bogda-console.service"
env_file="/etc/bogda/console.env"
asset_dir="/opt/bogda-console/frontend/dist/assets"
port="3101"
if [ -f "$env_file" ]; then
    parsed=$(awk -F= '/^BOGDA_CONSOLE_PUBLIC_PORT=/{gsub(/\r/,""); gsub(/"/,""); print $2; exit}' "$env_file")
    case "$parsed" in
        ''|*[!0-9]*) ;;
        3100)
            echo "BOGDA_CONSOLE_PUBLIC_PORT 3100 is reserved" >&2
            exit 78
            ;;
        *)
            port="$parsed"
            ;;
    esac
fi
base="http://127.0.0.1:$port"

usage() {
    echo "usage: $0 status|logs|restart|health" >&2
    exit 64
}

probe() {
    name=$1
    url=$2
    code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$url" || echo "000")
    echo "$name=$code"
    test "$code" = "200"
}

health_all() {
    probe root "$base/"
    js=$(ls -1 "$asset_dir"/*.js 2>/dev/null | head -n 1 || true)
    if [ -z "$js" ]; then
        echo "asset=missing"
        return 1
    fi
    probe asset "$base/assets/$(basename "$js")"
    probe api "$base/api/v1/capabilities"
}

wait_ready() {
    n=0
    while [ "$n" -lt 30 ]; do
        code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 2 "$base/" || echo "000")
        if [ "$code" = "200" ]; then
            echo "restart_http_code=$code"
            return 0
        fi
        n=$((n + 1))
        sleep 1
    done
    echo "restart_http_code=timeout"
    return 1
}

if [ "${1:-}" = "" ]; then
    usage
fi

case "$1" in
    status)
        systemctl is-enabled "$unit" || true
        systemctl is-active "$unit" || true
        systemctl --no-pager --full status "$unit" || true
        ;;
    logs)
        journalctl -u "$unit" -n 80 --no-pager
        echo "--- listen ---"
        ss -lntp 2>/dev/null | grep "$port" || true
        echo "--- serve ---"
        tailscale serve status 2>/dev/null || true
        ;;
    restart)
        sudo -n systemctl restart "$unit"
        wait_ready
        systemctl is-active "$unit"
        health_all
        ;;
    health)
        health_all
        ;;
    *)
        usage
        ;;
esac
