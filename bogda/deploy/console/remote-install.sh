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

if [ ! -f /etc/bogda/console.env ]; then
    umask 027
    grep -v '^#' "$STAGE/console.env.example" | grep -v '^$' > /etc/bogda/console.env
    if [ -f /etc/bogda/bogda.env ]; then
        awk -F= '/^PREFECT_API_AUTH_STRING=/{print}' /etc/bogda/bogda.env >> /etc/bogda/console.env
    fi
    chown root:bogda /etc/bogda/console.env
    chmod 0640 /etc/bogda/console.env
fi

install -m 0644 "$STAGE/bogda-console.service" /etc/systemd/system/bogda-console.service
systemctl daemon-reload
systemctl enable --now bogda-console.service
systemctl restart bogda-console.service
if command -v tailscale >/dev/null 2>&1; then
    tailscale serve --bg --http=3101 3101 || echo "WARN: tailscale serve failed; 3101 remains loopback"
fi
rm -rf "$STAGE"
systemctl is-active bogda-console.service
