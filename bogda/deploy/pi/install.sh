#!/usr/bin/env bash
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
project_dir="$(CDPATH= cd -- "$script_dir/../.." && pwd)"
unit_names="
bogda-prefect-server.service
bogda-pi-worker.service
bogda-prefect-snapshot.service
bogda-prefect-snapshot.timer
bogda-shadow-health.service
bogda-shadow-health.timer
"

usage() {
    echo "usage: $0 --dry-run | --install [--start] | --start-server | --start-services" >&2
    exit 64
}

validate_runtime_env() {
    env_file=$1
    assignment_count=0
    home_seen=false
    api_seen=false
    server_auth_seen=false
    client_auth_seen=false
    server_auth=
    client_auth=
    if [ -L "$env_file" ] || [ ! -f "$env_file" ]; then
        echo "runtime environment file must be a regular non-symlink file" >&2
        exit 1
    fi
    while IFS= read -r line || [ -n "$line" ]; do
        assignment_count=$((assignment_count + 1))
        case "$line" in
            PREFECT_HOME=/mnt/nas/.bogda/prefect)
                if [ "$home_seen" = true ]; then
                    echo "runtime environment has duplicate or invalid assignments" >&2
                    exit 1
                fi
                home_seen=true
                ;;
            PREFECT_API_URL=http://127.0.0.1:4200/api)
                if [ "$api_seen" = true ]; then
                    echo "runtime environment has duplicate or invalid assignments" >&2
                    exit 1
                fi
                api_seen=true
                ;;
            PREFECT_SERVER_API_AUTH_STRING=*)
                if [ "$server_auth_seen" = true ]; then
                    echo "runtime environment has duplicate or invalid assignments" >&2
                    exit 1
                fi
                server_auth=${line#PREFECT_SERVER_API_AUTH_STRING=}
                server_auth_seen=true
                ;;
            PREFECT_API_AUTH_STRING=*)
                if [ "$client_auth_seen" = true ]; then
                    echo "runtime environment has duplicate or invalid assignments" >&2
                    exit 1
                fi
                client_auth=${line#PREFECT_API_AUTH_STRING=}
                client_auth_seen=true
                ;;
            *)
                echo "runtime environment has duplicate or invalid assignments" >&2
                exit 1
                ;;
        esac
    done < "$env_file"
    if [ "$assignment_count" -ne 4 ] || [ "$home_seen" != true ] || [ "$api_seen" != true ] || \
        [ "$server_auth_seen" != true ] || [ "$client_auth_seen" != true ] || \
        [ -z "$server_auth" ] || [ -z "$client_auth" ] || \
        [ "$server_auth" = "SET_ON_PI_NOT_IN_GIT" ] || \
        [ "$client_auth" = "SET_ON_PI_NOT_IN_GIT" ] || \
        [ "$server_auth" != "$client_auth" ]; then
        echo "runtime environment has invalid authentication configuration" >&2
        exit 1
    fi
}

validate_managed_targets() {
    for target in \
        /etc/bogda/bogda.env \
        /etc/bogda/last-backup \
        /etc/systemd/system/bogda-prefect-server.service \
        /etc/systemd/system/bogda-pi-worker.service \
        /etc/systemd/system/bogda-prefect-snapshot.service \
        /etc/systemd/system/bogda-prefect-snapshot.timer \
        /etc/systemd/system/bogda-shadow-health.service \
        /etc/systemd/system/bogda-shadow-health.timer; do
        if [ -L "$target" ]; then
            echo "managed target must not be a symlink" >&2
            exit 1
        fi
    done
}

case "$#:${1:-}${2:+:${2:-}}" in
    1:--dry-run) mode=dry-run ; start=false ;;
    1:--install) mode=install ; start=false ;;
    2:--install:--start) mode=install ; start=true ;;
    1:--start-server) mode=start-server ; start=false ;;
    1:--start-services) mode=start-services ; start=false ;;
    *) usage ;;
esac

if [ -x /usr/local/bin/python3 ]; then
    python_bin=/usr/local/bin/python3
else
    python_bin="$(command -v python3 || true)"
fi
if [ -z "$python_bin" ]; then
    echo "python3 is required" >&2
    exit 1
fi

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$project_dir/src" "$python_bin" -m bogda.ops.bundle check "$script_dir"

if [ "$mode" = dry-run ]; then
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$project_dir/src" "$python_bin" -m bogda.ops.bundle dry-run "$script_dir"
    exit 0
fi

if [ "$mode" = install ]; then
    validate_managed_targets
    if [ "$start" = true ]; then
        if [ -f /etc/bogda/bogda.env ]; then
            validate_runtime_env /etc/bogda/bogda.env
        else
            validate_runtime_env "$script_dir/bogda.env.example"
        fi
    fi
fi

if [ "$mode" = start-server ] || [ "$mode" = start-services ]; then
    validate_runtime_env /etc/bogda/bogda.env
    if [ "$(id -u)" -ne 0 ]; then
        echo "$mode must run as root" >&2
        exit 1
    fi
    if ! command -v systemctl >/dev/null 2>&1; then
        echo "systemctl is required" >&2
        exit 1
    fi
    if [ "$mode" = start-server ]; then
        systemctl enable --now bogda-prefect-server.service
        exit 0
    fi
    if ! systemctl is-active --quiet bogda-prefect-server.service; then
        echo "bogda-prefect-server.service must be active before --start-services" >&2
        exit 1
    fi
    for unit_name in \
        bogda-pi-worker.service \
        bogda-prefect-snapshot.timer \
        bogda-shadow-health.timer; do
        systemctl enable --now "$unit_name"
    done
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "--install must run as root" >&2
    exit 1
fi

for required_command in uv getent useradd install findmnt systemctl; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        echo "$required_command is required" >&2
        exit 1
    fi
done

if [ "$(findmnt -no FSTYPE /mnt/nas)" != "ext4" ]; then
    echo "/mnt/nas must be an ext4 mount" >&2
    exit 1
fi

if ! getent passwd bogda >/dev/null 2>&1; then
    useradd --system --user-group --home /opt/bogda --create-home --shell /usr/sbin/nologin bogda
fi

install -d -m 0755 -o bogda -g bogda /opt/bogda
install -d -m 0750 -o root -g bogda /etc/bogda /etc/bogda/backups
install -d -m 0750 -o bogda -g bogda \
    /mnt/nas/.bogda/prefect \
    /mnt/nas/.bogda/snapshots \
    /mnt/nas/.bogda/manifests/health

backup_dir="/etc/bogda/backups/$(date -u +%Y%m%dT%H%M%SZ)"
if [ -e "$backup_dir" ]; then
    echo "backup directory already exists: $backup_dir" >&2
    exit 1
fi
install -d -m 0750 -o root -g bogda "$backup_dir"

backup_target() {
    target=$1
    if [ -e "$target" ]; then
        cp -p "$target" "$backup_dir/$(basename -- "$target")"
        printf '%s\tpresent\n' "$target" >> "$backup_dir/inventory.tsv"
    else
        printf '%s\tabsent\n' "$target" >> "$backup_dir/inventory.tsv"
    fi
}

backup_target /etc/bogda/bogda.env
for unit_name in $unit_names; do
    backup_target "/etc/systemd/system/$unit_name"
done
printf '%s\n' "$backup_dir" > /etc/bogda/last-backup

UV_PROJECT_ENVIRONMENT=/opt/bogda/.venv uv sync --frozen --no-dev --no-editable --project "$project_dir"

if [ ! -e /etc/bogda/bogda.env ]; then
    install -m 0640 -o root -g bogda "$script_dir/bogda.env.example" /etc/bogda/bogda.env
fi
chown root:bogda /etc/bogda/bogda.env
chmod 0640 /etc/bogda/bogda.env
for unit_name in $unit_names; do
    install -m 0644 -o root -g root "$script_dir/systemd/$unit_name" \
        "/etc/systemd/system/$unit_name"
done
systemctl daemon-reload

if [ "$start" = true ]; then
    for unit_name in \
        bogda-prefect-server.service \
        bogda-pi-worker.service \
        bogda-prefect-snapshot.timer \
        bogda-shadow-health.timer; do
        systemctl enable --now "$unit_name"
    done
fi
