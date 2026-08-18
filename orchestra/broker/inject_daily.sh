#!/usr/bin/env bash
# 每晚注入文献雷达任务（模板填充日期；幂等：当日已存在则跳过）
set -euo pipefail
D="$(date +%Y%m%d)"
TASK="/mnt/broker/tasks/T-${D}-nightly-radar.md"
[ -f "$TASK" ] && exit 0
sed "s/{{DATE}}/${D}/g" /home/liuxfs/broker/templates/nightly-radar.md > "$TASK"
echo "injected $TASK"
