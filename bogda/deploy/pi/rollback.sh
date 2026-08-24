#!/usr/bin/env bash
set -eu

unit_names="
bogda-prefect-server.service
bogda-pi-worker.service
bogda-prefect-snapshot.service
bogda-prefect-snapshot.timer
bogda-shadow-health.service
bogda-shadow-health.timer
"

usage() {
    echo "usage: $0 --dry-run | --apply" >&2
    exit 64
}

case "$#:${1:-}" in
    1:--dry-run) mode=dry-run ;;
    1:--apply) mode=apply ;;
    *) usage ;;
esac

if [ "$mode" = dry-run ]; then
    for unit_name in $unit_names; do
        printf 'ROLLBACK unit %s\n' "$unit_name"
    done
    if [ -e /etc/bogda/last-backup ]; then
        echo "CHECK backup pointer /etc/bogda/last-backup present"
    else
        echo "CHECK backup pointer /etc/bogda/last-backup absent"
    fi
    echo "ROLLBACK systemd daemon reload"
    echo "PRESERVE data root /mnt/nas/.bogda"
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "--apply must run as root" >&2
    exit 1
fi

if [ ! -f /etc/bogda/last-backup ]; then
    echo "missing /etc/bogda/last-backup" >&2
    exit 1
fi
backup_dir="$(cat /etc/bogda/last-backup)"
case "$backup_dir" in
    /etc/bogda/backups/*) ;;
    *)
        echo "backup path is outside /etc/bogda/backups" >&2
        exit 1
        ;;
esac
if [ "$backup_dir" = /etc/bogda/backups/ ] || [ ! -d "$backup_dir" ]; then
    echo "backup directory is invalid" >&2
    exit 1
fi
backup_dir="$(CDPATH= cd -- "$backup_dir" && pwd -P)"
case "$backup_dir" in
    /etc/bogda/backups/*) ;;
    *)
        echo "resolved backup path is outside /etc/bogda/backups" >&2
        exit 1
        ;;
esac
inventory="$backup_dir/inventory.tsv"
if [ ! -f "$inventory" ]; then
    echo "missing backup inventory" >&2
    exit 1
fi

validate_inventory() {
    seen_targets=""
    row_count=0
    while IFS="$(printf '\t')" read -r target status extra; do
        if [ -z "$target" ] || [ -z "$status" ] || [ -n "${extra:-}" ]; then
            echo "invalid inventory row" >&2
            exit 1
        fi
        case "$target" in
            /etc/bogda/bogda.env) ;;
            /etc/systemd/system/bogda-prefect-server.service) ;;
            /etc/systemd/system/bogda-pi-worker.service) ;;
            /etc/systemd/system/bogda-prefect-snapshot.service) ;;
            /etc/systemd/system/bogda-prefect-snapshot.timer) ;;
            /etc/systemd/system/bogda-shadow-health.service) ;;
            /etc/systemd/system/bogda-shadow-health.timer) ;;
            *)
                echo "inventory target is not managed" >&2
                exit 1
                ;;
        esac
        if [ -L "$target" ]; then
            echo "managed target must not be a symlink" >&2
            exit 1
        fi
        case "|$seen_targets|" in
            *"|$target|"*)
                echo "duplicate inventory target" >&2
                exit 1
                ;;
        esac
        seen_targets="${seen_targets}${target}|"
        row_count=$((row_count + 1))
        case "$status" in
            present)
                backup_file="$backup_dir/$(basename -- "$target")"
                if [ -L "$backup_file" ] || [ ! -f "$backup_file" ]; then
                    echo "backup source must be a regular non-symlink file" >&2
                    exit 1
                fi
                backup_parent="$(CDPATH= cd -- "$(dirname -- "$backup_file")" && pwd -P)"
                canonical_file="$backup_parent/$(basename -- "$backup_file")"
                if [ "$backup_parent" != "$backup_dir" ] || [ "$canonical_file" != "$backup_file" ]; then
                    echo "backup source resolves outside backup directory" >&2
                    exit 1
                fi
                ;;
            absent) ;;
            *)
                echo "unknown inventory status" >&2
                exit 1
                ;;
        esac
    done < "$inventory"
    if [ "$row_count" -ne 7 ]; then
        echo "inventory must contain all managed targets" >&2
        exit 1
    fi
}

apply_inventory() {
    while IFS="$(printf '\t')" read -r target status extra; do
        case "$status" in
            present) cp -p "$backup_dir/$(basename -- "$target")" "$target" ;;
            absent) rm -f "$target" ;;
        esac
    done < "$inventory"
}

validate_inventory
for unit_name in \
    bogda-prefect-server.service \
    bogda-pi-worker.service \
    bogda-prefect-snapshot.timer \
    bogda-shadow-health.timer; do
    systemctl disable --now "$unit_name"
done
apply_inventory

systemctl daemon-reload
