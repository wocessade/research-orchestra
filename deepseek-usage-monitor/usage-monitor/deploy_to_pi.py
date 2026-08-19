#!/usr/bin/env python3
"""部署脚本: SFTP 上传到树莓派并重启服务

用法:
  # 推荐: SSH 密钥
  set PI_HOST=192.168.0.223
  set PI_USER=liuxfs
  set PI_SSH_KEY=%USERPROFILE%\\.ssh\\id_rsa
  py -3 deploy_to_pi.py

  # 或密码 (勿把密码写进仓库)
  set PI_PASS=your_password
  py -3 deploy_to_pi.py

环境变量:
  PI_HOST       默认 192.168.0.200 (核桃派)
  PI_USER       默认 pi
  PI_PASS       密码 (与 PI_SSH_KEY 二选一)
  PI_SSH_KEY    私钥路径
  PI_PROJECT_DIR 默认 /home/<user>/usage-monitor
"""

from __future__ import annotations

import os
import sys

import paramiko

PI_HOST = os.getenv("PI_HOST", "192.168.0.200")
PI_USER = os.getenv("PI_USER", "pi")
PI_PASS = os.getenv("PI_PASS", "")
PI_SSH_KEY = os.getenv("PI_SSH_KEY", "")
PI_PROJECT_DIR = os.getenv(
    "PI_PROJECT_DIR", f"/home/{PI_USER}/usage-monitor"
)

FILES_TO_UPLOAD = [
    "app.py",
    "config.py",
    "eink_dashboard.py",
    "led_controller.py",
    "usage_scraper.py",
    "weather.py",
    "requirements.txt",
    "setup_pi.sh",
    "test_partial_buffer.py",
    "docs/dual_panel.md",
]

# 注意: 不上传 monitor.service —— 仓库里是 4B 旧时代的 unit (liuxfs/venv),
# 核桃派在役的是 monitor.walnutpi.service (pi/系统 python/LED 引脚不同)。
# systemd unit 与 MONITOR_TOKEN 由部署侧 (subsystem-4 Task 3) 在 Pi 上单独管理。
PI_COMMANDS = [
    f"cd {PI_PROJECT_DIR} && chmod +x setup_pi.sh 2>/dev/null; true",
    "fc-list :lang=zh 2>/dev/null | grep -qi wqy || sudo apt-get install -y fonts-wqy-microhei",
    "sudo systemctl daemon-reload",
    "sudo systemctl restart monitor",
    "sleep 2",
    "sudo systemctl status monitor --no-pager -l | head -25",
    "curl -sS http://127.0.0.1:5000/health || true",
]


def _connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    # 未知 host key 时警告并接受 (内网设备); 勿用于公网
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())

    kwargs = {
        "hostname": PI_HOST,
        "username": PI_USER,
        "timeout": 15,
        "allow_agent": True,
        "look_for_keys": True,
    }
    if PI_SSH_KEY:
        kwargs["key_filename"] = os.path.expanduser(PI_SSH_KEY)
    elif PI_PASS:
        kwargs["password"] = PI_PASS
    else:
        # 仍尝试 agent / 默认密钥
        pass

    try:
        ssh.connect(**kwargs)
    except paramiko.SSHException:
        # 首次连接: 允许一次性写入 known_hosts 需用户确认 — 这里给出清晰错误
        raise
    return ssh


def sftp_transfer() -> None:
    print(f"=== 连接 {PI_USER}@{PI_HOST} ===")
    if not PI_PASS and not PI_SSH_KEY:
        print(
            "提示: 未设置 PI_PASS / PI_SSH_KEY, 将尝试本机 SSH agent / 默认密钥",
            flush=True,
        )

    try:
        ssh = _connect()
    except paramiko.AuthenticationException:
        print(
            f"认证失败: {PI_USER}@{PI_HOST}\n"
            "请设置环境变量 PI_SSH_KEY 或 PI_PASS (不要把密码写进代码)",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            f"连接失败: {e}\n"
            "若是 host key 未知: 先在本机执行 "
            f"ssh {PI_USER}@{PI_HOST} 接受指纹",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        sftp = ssh.open_sftp()
        print("SFTP connected\n")
        src_dir = os.path.dirname(os.path.abspath(__file__))

        # 确保远程子目录存在 (如 docs/)
        remote_dirs = {os.path.dirname(n).replace("\\", "/") for n in FILES_TO_UPLOAD}
        for d in sorted(remote_dirs):
            if not d or d == ".":
                continue
            remote_dir = f"{PI_PROJECT_DIR}/{d}"
            try:
                sftp.stat(remote_dir)
            except OSError:
                print(f"  [MKDIR] {d}")
                sftp.mkdir(remote_dir)

        for name in FILES_TO_UPLOAD:
            local_path = os.path.join(src_dir, name)
            remote_name = name.replace("\\", "/")
            remote_path = f"{PI_PROJECT_DIR}/{remote_name}"
            if not os.path.exists(local_path):
                print(f"  [SKIP] Missing: {name}")
                continue
            print(f"  [SEND] {name}")
            sftp.put(local_path, remote_path)
            print(f"  [OK]   {name}")

        sftp.close()
        print("\n文件上传完成\n=== 执行 Pi 端命令 ===")

        for cmd in PI_COMMANDS:
            print(f"\n$ {cmd}")
            _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            if out:
                print(out)
            if err:
                print(f"[stderr] {err}")

        print("\n=== 部署完成 ===")
    finally:
        ssh.close()


if __name__ == "__main__":
    sftp_transfer()
