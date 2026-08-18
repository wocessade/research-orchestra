#!/usr/bin/env bash
# 4B → 核桃派冷备：rsync over ssh 增量镜像（systemd timer 每日 03:00 触发）
# 用法（在 4B 上）: bash backup_to_nas.sh [源目录]（默认 /home/liuxfs/broker-data）
set -euo pipefail

NAS_USER="${ORCHESTRA_NAS_USER:-pi}"
NAS_HOST="${ORCHESTRA_NAS_HOST:-192.168.0.200}"
SRC="${1:-/home/liuxfs/broker-data}"
DST_ROOT="/home/pi/backup/broker"
LOG="${SRC}/logs/backup.log"
TS="$(date -Iseconds)"

echo "$TS [backup] start src=$SRC -> $NAS_USER@$NAS_HOST:$DST_ROOT" >> "$LOG"

# SQLite 一致性快照：live db 边写边拷可能损坏，先 .backup 出稳定副本再同步
if command -v sqlite3 >/dev/null 2>&1 && [ -f "$SRC/db/broker.db" ]; then
  sqlite3 "$SRC/db/broker.db" ".backup '$SRC/db/broker.db.snapshot'" 2>>"$LOG" || true
fi

if rsync -a --delete -e "ssh -o BatchMode=yes" \
     "$SRC/results" "$SRC/logs" "$SRC/db" \
     "$NAS_USER@$NAS_HOST:$DST_ROOT/" >> "$LOG" 2>&1; then
  echo "$(date -Iseconds) [backup] done OK" >> "$LOG"
else
  echo "$(date -Iseconds) [backup] FAILED rc=$?" >> "$LOG"
  exit 1
fi
