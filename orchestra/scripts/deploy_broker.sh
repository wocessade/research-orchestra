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
ssh "$SSH_USER@$SSH_HOST" 'mkdir -p /home/liuxfs/broker /home/liuxfs/broker/templates'
scp -q "$ROOT"/broker/{db.py,taskfile.py,executor.py,dispatcher.py,__init__.py,inject_daily.sh,housekeeping.sh,send_email.py,config.example.json} "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/"
scp -q "$ROOT"/scripts/backup_to_nas.sh "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/"  # 审计 CONCERN-1：备份脚本本体此前从未随 deploy 传载
scp -q "$ROOT"/templates/nightly-radar.md "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/templates/"
scp -q "$ROOT"/broker/orchestra-broker.service "$ROOT"/broker/orchestra-timer.timer "$ROOT"/broker/orchestra-timer.service "$ROOT"/broker/orchestra-backup.service "$ROOT"/broker/orchestra-backup.timer "$ROOT"/broker/orchestra-backup-alert.service "$ROOT"/broker/orchestra-housekeeping.service "$ROOT"/broker/orchestra-housekeeping.timer "$ROOT"/broker/logrotate-orchestra.conf "$SSH_USER@$SSH_HOST:/tmp/"

# 2) 远端：目录 + config.json（不存在时从 example 生成，路径按 REMOTE_ROOT 改写）
ssh "$SSH_USER@$SSH_HOST" "REMOTE_ROOT='$REMOTE_ROOT' bash -s" << 'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_ROOT"/{tasks,results,logs,db}
cd /home/liuxfs/broker
if [ ! -f config.json ]; then
  sed -e "s|/mnt/broker|$REMOTE_ROOT|g" config.example.json > config.json
  chmod 600 config.json
fi
sudo mv /tmp/orchestra-broker.service /tmp/orchestra-timer.timer /tmp/orchestra-timer.service /tmp/orchestra-backup.service /tmp/orchestra-backup.timer /tmp/orchestra-backup-alert.service /tmp/orchestra-housekeeping.service /tmp/orchestra-housekeeping.timer /etc/systemd/system/
sudo mv /tmp/logrotate-orchestra.conf /etc/logrotate.d/orchestra-broker
sudo cp /home/liuxfs/broker/send_email.py /usr/local/bin/ && sudo chmod 755 /usr/local/bin/send_email.py
# service 内日志路径按 REMOTE_ROOT 改写（避免日志落到未挂载点）
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/systemd/system/orchestra-broker.service
# 审计 CONCERN-1：备份告警 unit 与备份脚本的源路径也必须随 REMOTE_ROOT 改写，否则迁移后静默备份旧副本
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/systemd/system/orchestra-backup-alert.service
sed -i "s|/mnt/broker|$REMOTE_ROOT|g" /home/liuxfs/broker/backup_to_nas.sh
# inject_daily.sh / housekeeping.sh / logrotate 中的路径按 REMOTE_ROOT 改写
sed -i "s|/mnt/broker/tasks|$REMOTE_ROOT/tasks|g; s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /home/liuxfs/broker/inject_daily.sh /home/liuxfs/broker/housekeeping.sh
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/logrotate.d/orchestra-broker
# 审计 INFO-5：新机器部署时凭据 drop-in 缺失会导致 dsh/邮件静默失败，主动告警
if [ ! -f /etc/systemd/system/orchestra-broker.service.d/env.conf ]; then
  echo "WARN: env.conf 缺失！DEEPSEEK_API_KEY / SMTP 凭据未配置，dsh 任务与邮件会失败。"
fi
sudo systemctl daemon-reload
sudo systemctl enable --now orchestra-broker.service
sudo systemctl enable --now orchestra-timer.timer
sudo systemctl enable --now orchestra-backup.timer
sudo systemctl enable --now orchestra-housekeeping.timer
# 审计 CONCERN-2：enable --now 对已 active 的 service 是 no-op，必须显式重启使新代码生效
sudo systemctl restart orchestra-broker.service
sudo systemctl status orchestra-broker.service --no-pager | head -5
REMOTE
echo "部署完成（remote root: $REMOTE_ROOT）"
