"""上传代码到核桃派并安装依赖 (任务 #6)"""
import os
import sys
import paramiko

HOST = "192.168.0.200"
USER = "pi"
PASS = "123456"

LOCAL = r"D:\pythonProject\deepseek-usage-monitor\usage-monitor"
AUTH_SRC = r"D:\backup\rpi-backup-20260801\extracted\auth_state.json"
REMOTE = "/home/pi/usage-monitor"

# (本地相对路径, 远程相对路径) — monitor.walnutpi.service 重命名部署为 monitor.service
FILES = [
    ("app.py", "app.py"),
    ("config.py", "config.py"),
    ("eink_dashboard.py", "eink_dashboard.py"),
    ("led_controller.py", "led_controller.py"),
    ("usage_scraper.py", "usage_scraper.py"),
    ("weather.py", "weather.py"),
    ("requirements.txt", "requirements.txt"),
    ("monitor.walnutpi.service", "monitor.service"),
    (os.path.join("waveshare_epd", "epd3in97.py"), os.path.join("waveshare_epd", "epd3in97.py")),
    (os.path.join("waveshare_epd", "epdconfig.py"), os.path.join("waveshare_epd", "epdconfig.py")),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = ssh.open_sftp()

def mkdir_p(path):
    parts = path.split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)

mkdir_p(REMOTE)
mkdir_p(REMOTE + "/waveshare_epd")

for local_rel, remote_rel in FILES:
    local_path = os.path.join(LOCAL, local_rel)
    remote_path = REMOTE + "/" + remote_rel
    sftp.put(local_path, remote_path)
    print(f"uploaded {local_rel} -> {remote_path}")

# auth_state.json 用树莓派备份里的最新版
sftp.put(AUTH_SRC, REMOTE + "/auth_state.json")
print(f"uploaded auth_state.json (from rpi backup) -> {REMOTE}/auth_state.json")
sftp.close()

def run(cmd):
    _, out, err = ssh.exec_command(cmd)
    out_s = out.read().decode(errors="replace")
    err_s = err.read().decode(errors="replace")
    print(f"$ {cmd}\n{out_s}{err_s}")
    return out_s + err_s

# 检查 apt 包可用性
run("apt-cache policy python3-lgpio python3-gpiozero python3-spidev python3-flask python3-pil python3-requests python3-apscheduler | grep -E '^[a-z]|Candidate'")

ssh.close()
print("DONE - 依赖安装另行执行")
