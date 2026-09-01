#!/bin/sh
# Runs on RK3528 as root (sudo). Invoked by deploy_console.sh. No secrets printed.
set -eu

STAGE=${1:?stage dir}
APP=/opt/bogda-console
# Windows checkouts may ship CRLF.
sed -i 's/\r$//' "$STAGE/maintain.sh" "$STAGE/remote-install.sh" "$STAGE/bogda-console.service" 2>/dev/null || true

install -d -o bogda -g bogda "$APP"
rm -rf "$APP/src" "$APP/frontend"
mkdir -p "$APP/frontend"
if [ ! -f "$STAGE/fixtures/normal-active.json" ]; then
    echo "stage fixtures missing; refusing install (create_app always loads them)" >&2
    exit 1
fi
cp -a "$STAGE/src" "$APP/src"
cp -a "$STAGE/pyproject.toml" "$APP/pyproject.toml"
cp -a "$STAGE/dist" "$APP/frontend/dist"
cp -a "$STAGE/fixtures" "$APP/fixtures"
install -m 0755 "$STAGE/maintain.sh" "$APP/maintain.sh"
install -m 0644 "$STAGE/dsh-maintain.md" "$APP/dsh-maintain.md"
chown -R bogda:bogda "$APP/src" "$APP/frontend" "$APP/pyproject.toml" "$APP/fixtures" "$APP/maintain.sh" "$APP/dsh-maintain.md"

if [ ! -x "$APP/.venv/bin/python" ]; then
    sudo -u bogda env HOME="$APP" UV_NO_CONFIG=1 uv venv --python /opt/bogda/.venv/bin/python "$APP/.venv"
fi
sudo -u bogda env HOME="$APP" UV_NO_CONFIG=1 uv pip install --python "$APP/.venv/bin/python" -e "$APP"

append_missing_key() {
    dest=/etc/bogda/console.env
    key=$1
    src=$2
    if [ ! -f "$dest" ] || [ ! -f "$src" ]; then
        return 0
    fi
    python3 - "$dest" "$key" "$src" <<'PY'
from pathlib import Path
import sys

dest = Path(sys.argv[1])
key = sys.argv[2]
src = Path(sys.argv[3])
existing = dest.read_text(encoding="utf-8")
if any(line.startswith(f"{key}=") for line in existing.splitlines()):
    raise SystemExit(0)
plain = f"{key}="
env_plain = f"Environment={key}="
env_quoted = f'Environment="{key}='
for raw in src.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    value = None
    if line.startswith(plain):
        value = line
    elif line.startswith(env_quoted):
        value = line[len("Environment="):].strip('"')
    elif line.startswith(env_plain):
        value = line[len("Environment="):]
    if value:
        with dest.open("a", encoding="utf-8") as handle:
            handle.write(value + "\n")
        break
PY
}

if [ ! -f /etc/bogda/console.env ]; then
    umask 027
    grep -v '^#' "$STAGE/console.env.example" | grep -v '^$' > /etc/bogda/console.env
fi
append_missing_key PREFECT_API_AUTH_STRING /etc/bogda/bogda.env
append_missing_key DEEPSEEK_API_KEY /etc/bogda/bogda.env
append_missing_key DEEPSEEK_API_KEY /etc/systemd/system/orchestra-broker.service.d/env.conf
chown root:bogda /etc/bogda/console.env
chmod 0640 /etc/bogda/console.env

install -m 0644 "$STAGE/bogda-console.service" /etc/systemd/system/bogda-console.service
systemctl daemon-reload
systemctl enable --now bogda-console.service
systemctl restart bogda-console.service
if command -v tailscale >/dev/null 2>&1; then
    port=3101
    if [ -f /etc/bogda/console.env ]; then
        parsed=$(awk -F= '/^BOGDA_CONSOLE_PUBLIC_PORT=/{gsub(/\r/,""); gsub(/"/,""); print $2; exit}' /etc/bogda/console.env)
        case "$parsed" in
            ''|*[!0-9]*) ;;
            3100)
                echo "BOGDA_CONSOLE_PUBLIC_PORT 3100 is reserved" >&2
                exit 78
                ;;
            *) port=$parsed ;;
        esac
    fi
    tailscale serve --bg --http="$port" "$port" || echo "WARN: tailscale serve failed; $port remains loopback"
fi
rm -rf "$STAGE"
systemctl is-active bogda-console.service
