#!/usr/bin/env bash
# 周常维护：清理 14 天前的 dsh 会话日志；磁盘余量告警
set -euo pipefail
LOG="/mnt/broker/logs/housekeeping.log"
echo "$(date -Iseconds) [housekeeping] start" >> "$LOG"
find ~/.dsh/sessions -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null
AVAIL=$(df -m / | awk 'NR==2{print $4}')
echo "$(date -Iseconds) [housekeeping] avail=${AVAIL}MiB" >> "$LOG"
if [ "$AVAIL" -lt 1500 ]; then
  echo "$(date -Iseconds) [ALERT] disk low: ${AVAIL}MiB available" >> "$LOG"
fi
