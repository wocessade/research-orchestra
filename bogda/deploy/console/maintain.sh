#!/bin/sh
# Box-side 3101 maintenance. dsh may only call this script.
# Allowed verbs: status | logs | restart | health
# Does not print /etc/bogda/console.env or bogda.env.

set -eu

unit="bogda-console.service"
health_url="http://127.0.0.1:3101/"

usage() {
    echo "usage: $0 status|logs|restart|health" >&2
    exit 64
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
        ;;
    restart)
        sudo -n systemctl restart "$unit"
        systemctl is-active "$unit"
        ;;
    health)
        code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$health_url" || echo "000")
        echo "http_code=$code"
        test "$code" = "200"
        ;;
    *)
        usage
        ;;
esac
