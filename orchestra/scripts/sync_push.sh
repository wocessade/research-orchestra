#!/usr/bin/env bash
# 推送 tasks/ 下全部任务文件到 4B Broker（幂等：Broker 按 slug 去重）
set -euo pipefail
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
