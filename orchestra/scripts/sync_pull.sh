#!/usr/bin/env bash
# 从 4B Broker 拉取 results/ 与 logs/（增量覆盖本地同名文件）
set -euo pipefail
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash sync_pull.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
scp -rq "$SSH_USER@$SSH_HOST:/mnt/broker/results/." "$ROOT/results/"
scp -rq "$SSH_USER@$SSH_HOST:/mnt/broker/logs/." "$ROOT/logs/"
echo "已拉取 results/ 与 logs/"
