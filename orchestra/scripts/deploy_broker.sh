#!/usr/bin/env bash
# 部署 broker 代码到 4B 并 (re)start systemd 服务
# 用法: ORCHESTRA_SSH_HOST=192.168.x.x [ORCHESTRA_REMOTE_ROOT=~/broker-data] bash deploy_broker.sh
# SSD 已挂载时 ORCHESTRA_REMOTE_ROOT 默认 /mnt/broker；SD 过渡期传 ~/broker-data
set -euo pipefail
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash deploy_broker.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
REMOTE_ROOT="${ORCHESTRA_REMOTE_ROOT:-/mnt/broker}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUARD_REMOTE="/tmp/orchestra-migration-guard-$$.py"

# 1) 只把迁移门禁传到 /tmp 并预检。预检通过前不得覆盖任何在役代码、模板或 unit。
cleanup_guard() {
  ssh "$SSH_USER@$SSH_HOST" "rm -f '$GUARD_REMOTE'" >/dev/null 2>&1 || true
}
trap cleanup_guard EXIT
scp -q "$ROOT/broker/migration_guard.py" "$SSH_USER@$SSH_HOST:$GUARD_REMOTE"
ssh "$SSH_USER@$SSH_HOST" "REMOTE_ROOT='$REMOTE_ROOT' GUARD_REMOTE='$GUARD_REMOTE' bash -s" << 'PREFLIGHT'
set -euo pipefail
mkdir -p "$REMOTE_ROOT"/{tasks,db}
guard_args=(
  --tasks-dir "$REMOTE_ROOT/tasks"
  --db-path "$REMOTE_ROOT/db/broker.db"
)
if [ -f /home/liuxfs/broker/config.json ]; then
  guard_args+=(--config /home/liuxfs/broker/config.json)
fi
python3 "$GUARD_REMOTE" "${guard_args[@]}"
PREFLIGHT
cleanup_guard
trap - EXIT

# 2) 预检通过后先停旧 broker（M-6）：stop 至末尾 restart 之间无在役进程，
#    门禁快照与文件覆盖间的 TOCTOU 窗口归零；unit 未安装（首部署）时 stop 失败可容忍。
broker_stopped=false
if ssh "$SSH_USER@$SSH_HOST" 'sudo systemctl stop orchestra-broker.service' >/dev/null 2>&1; then
  broker_stopped=true
fi
recover_broker() {
  # 失败兜底：stop 后中途失败时把 broker 拉起来（部分覆盖的旧代码也比长期停机好）
  if [ "$broker_stopped" = true ]; then
    ssh "$SSH_USER@$SSH_HOST" 'sudo systemctl start orchestra-broker.service' >/dev/null 2>&1 || true
  fi
}
trap recover_broker EXIT

# 3) 预检通过后才传在役代码、模板和 unit
ssh "$SSH_USER@$SSH_HOST" 'mkdir -p /home/liuxfs/broker /home/liuxfs/broker/templates'
scp -q "$ROOT"/broker/{db.py,taskfile.py,executor.py,dispatcher.py,artifact_validators.py,radar_render.py,radar_notify.py,migration_guard.py,exam_watch.py,__init__.py,inject_daily.sh,housekeeping.sh,send_email.py,config.example.json} "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/"
scp -q "$ROOT"/scripts/backup_to_nas.sh "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/"  # 审计 CONCERN-1：备份脚本本体此前从未随 deploy 传载
scp -q "$ROOT"/templates/nightly-radar-*.md "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/templates/"
scp -q "$ROOT"/broker/orchestra-broker.service "$ROOT"/broker/orchestra-timer.timer "$ROOT"/broker/orchestra-timer.service "$ROOT"/broker/orchestra-backup.service "$ROOT"/broker/orchestra-backup.timer "$ROOT"/broker/orchestra-backup-alert.service "$ROOT"/broker/orchestra-housekeeping.service "$ROOT"/broker/orchestra-housekeeping.timer "$ROOT"/broker/orchestra-exam-watch.service "$ROOT"/broker/orchestra-exam-watch.timer "$ROOT"/broker/logrotate-orchestra.conf "$SSH_USER@$SSH_HOST:/tmp/"
# Windows scp 可能带 CRLF；远端立刻剥 CR，避免 inject_daily 因 pipefail\r 退出
ssh "$SSH_USER@$SSH_HOST" "sed -i 's/\r$//' /home/liuxfs/broker/*.sh /home/liuxfs/broker/templates/*.md"

# 4) 远端：目录 + config.json（不存在时从 example 生成，路径按 REMOTE_ROOT 改写）
ssh "$SSH_USER@$SSH_HOST" "REMOTE_ROOT='$REMOTE_ROOT' bash -s" << 'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_ROOT"/{tasks,results,logs,db}
cd /home/liuxfs/broker
if [ ! -f config.json ]; then
  sed -e "s|/mnt/broker|$REMOTE_ROOT|g" config.example.json > config.json
  chmod 600 config.json
fi
# 四阶段模板替代旧单体模板；删除远端遗留，避免旧定时脚本或人工误注入。
rm -f templates/nightly-radar.md
sudo mv /tmp/orchestra-broker.service /tmp/orchestra-timer.timer /tmp/orchestra-timer.service /tmp/orchestra-backup.service /tmp/orchestra-backup.timer /tmp/orchestra-backup-alert.service /tmp/orchestra-housekeeping.service /tmp/orchestra-housekeeping.timer /tmp/orchestra-exam-watch.service /tmp/orchestra-exam-watch.timer /etc/systemd/system/
sudo mv /tmp/logrotate-orchestra.conf /etc/logrotate.d/orchestra-broker
sudo cp /home/liuxfs/broker/send_email.py /usr/local/bin/ && sudo chmod 755 /usr/local/bin/send_email.py
# service 内日志路径按 REMOTE_ROOT 改写（避免日志落到未挂载点）
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/systemd/system/orchestra-broker.service
# 审计 CONCERN-1：备份告警 unit 与备份脚本的源路径也必须随 REMOTE_ROOT 改写，否则迁移后静默备份旧副本
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/systemd/system/orchestra-backup-alert.service
sudo sed -i "s|/mnt/broker|$REMOTE_ROOT|g" /etc/systemd/system/orchestra-exam-watch.service
sed -i "s|/mnt/broker|$REMOTE_ROOT|g" /home/liuxfs/broker/backup_to_nas.sh
# inject_daily.sh / housekeeping.sh / logrotate 中的路径按 REMOTE_ROOT 改写
sed -i "s|/mnt/broker/tasks|$REMOTE_ROOT/tasks|g; s|/mnt/broker/results|$REMOTE_ROOT/results|g; s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /home/liuxfs/broker/inject_daily.sh /home/liuxfs/broker/housekeeping.sh
sudo sed -i "s|/mnt/broker/logs|$REMOTE_ROOT/logs|g" /etc/logrotate.d/orchestra-broker
# 审计 INFO-5：新机器部署时凭据 drop-in 缺失会导致 dsh/邮件静默失败，主动告警
if [ ! -f /etc/systemd/system/orchestra-broker.service.d/env.conf ]; then
  echo "WARN: env.conf 缺失！DEEPSEEK_API_KEY / SMTP 凭据未配置，dsh 任务与邮件会失败。"
fi
# exam-watch 邮件同样需要 SMTP 凭据；它用与 broker 相同的 drop-in 机制（EnvironmentFile 复用 broker 文件会因格式不兼容注入失败）
if [ ! -f /etc/systemd/system/orchestra-exam-watch.service.d/env.conf ]; then
  echo "WARN: exam-watch 的 env.conf 缺失！请从 orchestra-broker.service.d/env.conf 复制到 orchestra-exam-watch.service.d/ 并 chmod 600，否则考试邮件通知会失败。"
fi
sudo systemctl daemon-reload
sudo systemctl enable --now orchestra-broker.service
sudo systemctl enable --now orchestra-timer.timer
sudo systemctl enable --now orchestra-backup.timer
sudo systemctl enable --now orchestra-housekeeping.timer
sudo systemctl enable --now orchestra-exam-watch.timer
# 审计 CONCERN-2：enable --now 对已 active 的 service 是 no-op，必须显式重启使新代码生效
sudo systemctl restart orchestra-broker.service
sudo systemctl status orchestra-broker.service --no-pager | head -5
REMOTE
trap - EXIT
echo "部署完成（remote root: $REMOTE_ROOT）"
