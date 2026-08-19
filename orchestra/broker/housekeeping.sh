#!/usr/bin/env bash
# 周常维护：清理 14 天前的 dsh 会话日志；磁盘余量告警（根分区与 broker 数据盘分别检查）
# 告警除写日志外还发邮件（哨兵审计 CONCERN-7：仅落日志无人知晓）
set -euo pipefail
LOG="/mnt/broker/logs/housekeeping.log"
echo "$(date -Iseconds) [housekeeping] start" >> "$LOG"
find ~/.dsh/sessions -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null

ALERT=""
for PART in / /mnt/broker; do
  if ! df -m "$PART" >/dev/null 2>&1; then
    echo "$(date -Iseconds) [housekeeping] $PART not mounted, skip" >> "$LOG"
    continue
  fi
  AVAIL=$(df -m "$PART" | awk 'NR==2{print $4}')
  echo "$(date -Iseconds) [housekeeping] $PART avail=${AVAIL}MiB" >> "$LOG"
  if [ "$AVAIL" -lt 1500 ]; then
    ALERT="${ALERT}${PART} low: ${AVAIL}MiB; "
  fi
done

if [ -n "$ALERT" ]; then
  echo "$(date -Iseconds) [ALERT] disk low: $ALERT" >> "$LOG"
  echo "磁盘余量告警: $ALERT（4B broker，请检查）" > /tmp/housekeeping-alert.txt
  if python3 /usr/local/bin/send_email.py "[orchestra] 磁盘告警" /tmp/housekeeping-alert.txt 2>>"$LOG"; then
    echo "$(date -Iseconds) [housekeeping] alert email sent" >> "$LOG"
  else
    echo "$(date -Iseconds) [housekeeping] FAILED alert email" >> "$LOG"
  fi
fi
