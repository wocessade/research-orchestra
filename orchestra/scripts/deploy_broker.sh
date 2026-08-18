#!/usr/bin/env bash
# 部署 broker 代码到 4B 并 (re)start systemd 服务
# 用法: ORCHESTRA_SSH_HOST=192.168.x.x [ORCHESTRA_REMOTE_ROOT=~/broker-data] bash deploy_broker.sh
# SSD 已挂载时 ORCHESTRA_REMOTE_ROOT 默认 /mnt/broker；SD 过渡期传 ~/broker-data
set -euo pipefail
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash deploy_broker.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
REMOTE_ROOT="${ORCHESTRA_REMOTE_ROOT:-/mnt/broker}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 1) 传代码
ssh "$SSH_USER@$SSH_HOST" 'mkdir -p /home/liuxfs/broker'
scp -q "$ROOT"/broker/{db.py,taskfile.py,executor.py,dispatcher.py,__init__.py,inject_daily.sh,config.example.json} "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/"
scp -q "$ROOT"/broker/orchestra-broker.service "$ROOT"/broker/orchestra-timer.timer "$ROOT"/broker/orchestra-timer.service "$SSH_USER@$SSH_HOST:/tmp/"

# 2) 远端：目录 + config.json（不存在时从 example 生成，路径按 REMOTE_ROOT 改写）
ssh "$SSH_USER@$SSH_HOST" "REMOTE_ROOT='$REMOTE_ROOT' bash -s" << 'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_ROOT"/{tasks,results,logs,db}
cd /home/liuxfs/broker
if [ ! -f config.json ]; then
  sed -e "s|/mnt/broker|$REMOTE_ROOT|g" config.example.json > config.json
  chmod 600 config.json
fi
sudo mv /tmp/orchestra-broker.service /tmp/orchestra-timer.timer /tmp/orchestra-timer.service /etc/systemd/system/
# service 内日志路径按 REMOTE_ROOT 改写（避免日志落到未挂载点）
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/systemd/system/orchestra-broker.service
# inject_daily.sh 与 service 文件中的任务路径按 REMOTE_ROOT 改写
sed -i "s|/mnt/broker/tasks|$REMOTE_ROOT/tasks|g" /home/liuxfs/broker/inject_daily.sh
sudo systemctl daemon-reload
sudo systemctl enable --now orchestra-broker.service
sudo systemctl enable --now orchestra-timer.timer
sudo systemctl status orchestra-broker.service --no-pager | head -5
REMOTE
echo "部署完成（remote root: $REMOTE_ROOT）"
