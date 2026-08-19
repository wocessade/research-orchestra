#!/usr/bin/env bash
# 推送 tasks/ 下全部任务文件到 4B Broker（幂等：Broker 按 slug 去重）
set -euo pipefail
ORCHESTRA_MONITOR_API="${ORCHESTRA_MONITOR_API:-http://192.168.0.200:5000/api/orchestra}"
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash sync_push.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
REMOTE_ROOT="${ORCHESTRA_REMOTE_ROOT:-/mnt/broker}"   # SSD 挂载点；SD 过渡期可用 ~/broker-data
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
shopt -s nullglob
files=("$ROOT"/tasks/T-*.md)
if [ ${#files[@]} -eq 0 ]; then
  echo "无待推送任务（tasks/ 下没有 T-*.md）"
  exit 0
fi
scp -q "${files[@]}" "$SSH_USER@$SSH_HOST:$REMOTE_ROOT/tasks/"
echo "已推送 ${#files[@]} 个任务文件"

# 可选: 同步动作后上报 last_sync 到仪表盘 (subsystem-4)
# 需设 ORCHESTRA_MONITOR_TOKEN 才生效; 失败静默不阻塞同步
report_last_sync() {
  if [ -n "${ORCHESTRA_MONITOR_TOKEN:-}" ]; then
    curl -s -m 5 -X POST \
      -H "Content-Type: application/json" \
      -H "X-Monitor-Token: ${ORCHESTRA_MONITOR_TOKEN}" \
      -d "{\"last_sync\": $(date +%s), \"source\": \"sync\"}" \
      "$ORCHESTRA_MONITOR_API" >/dev/null 2>&1 || true
  fi
}
report_last_sync
