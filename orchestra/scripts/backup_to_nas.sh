#!/usr/bin/env bash
# 4B → 核桃派冷备：rsync over ssh 增量镜像（systemd timer 每日 03:00 触发）
# 用法（在 4B 上）: bash backup_to_nas.sh [源目录]（默认 /home/liuxfs/broker-data）
# 恢复约定：NAS db/ 下只有 broker.db.snapshot 是恢复用一致副本（live db/wal/shm 不同步）
set -euo pipefail

NAS_USER="${ORCHESTRA_NAS_USER:-pi}"
NAS_HOST="${ORCHESTRA_NAS_HOST:-192.168.0.200}"
SRC="${1:-/home/liuxfs/broker-data}"
DST_ROOT="/home/pi/backup/broker"
LOG="${SRC}/logs/backup.log"
TS="$(date -Iseconds)"

echo "$TS [backup] start src=$SRC -> $NAS_USER@$NAS_HOST:$DST_ROOT" >> "$LOG"

# SQLite 一致性快照：live db 边写边拷可能损坏。快照失败 = 备份失败（哨兵审计：勿静默）
if [ -f "$SRC/db/broker.db" ]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$SRC/db/broker.db" ".backup '$SRC/db/broker.db.snapshot'" 2>>"$LOG" \
      || { echo "$(date -Iseconds) [backup] FAILED sqlite snapshot" >> "$LOG"; exit 1; }
  else
    echo "$(date -Iseconds) [backup] FAILED sqlite3 not installed" >> "$LOG"
    exit 1
  fi
fi

if rsync -a --delete \
     --exclude='broker.db-wal' --exclude='broker.db-shm' \
     -e "ssh -o BatchMode=yes" \
     "$SRC/results" "$SRC/logs" "$SRC/db" \
     "$NAS_USER@$NAS_HOST:$DST_ROOT/" >> "$LOG" 2>&1; then
  echo "$(date -Iseconds) [backup] done OK" >> "$LOG"
else
  rc=$?
  echo "$(date -Iseconds) [backup] FAILED rsync rc=$rc" >> "$LOG"
  exit 1
fi
