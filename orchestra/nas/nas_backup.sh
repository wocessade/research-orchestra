#!/usr/bin/env bash
# 4B 兼职冷备 NAS：/mnt/broker 本地 rsync 镜像到 /mnt/nas（WD 250G, fstab nofail）
# systemd timer 每日 04:17 触发（nas-backup.timer）
set -euo pipefail

if ! mountpoint -q /mnt/nas; then
  echo "$(date -Iseconds) [nas-backup] SKIP: /mnt/nas not mounted"
  exit 0
fi

mkdir -p /mnt/nas/backup/broker
rsync -a --delete /mnt/broker/results/ /mnt/nas/backup/broker/results/
rsync -a --delete /mnt/broker/logs/ /mnt/nas/backup/broker/logs/
echo "backup done: $(date -Iseconds)"
