# DeepSeek 用量监控 (树莓派 + 墨水屏)

> 套件根目录：[`../`](../)（`deepseek-usage-monitor/`）

硬件: Waveshare **3.97"** e-Paper HAT+ (800×480)、双色 LED (BCM 5/6)、Raspberry Pi 4B。

## 功能

- DeepSeek 余额 API (60s)
- Platform 用量抓取 (cookie REST；Playwright 回退默认关闭)
- Windows Claude Code hooks → LED + 墨水屏状态（**已停用**；`/api/status` 仍保留，无害）
- 全幅局刷波形 (~0.6s，无闪烁) + 30min 强制全刷

## 树莓派

```bash
cd ~/usage-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install lgpio
# 仅当 ENABLE_PLAYWRIGHT_FALLBACK=1 时需要:
# pip install playwright && playwright install chromium

# 登录 DeepSeek Platform (需显示器/VNC)，生成 auth_state.json
python usage_scraper.py login

sudo cp monitor.service /etc/systemd/system/
sudo systemctl edit monitor   # 填入真实 DEEPSEEK_API_KEY / 可选 MONITOR_TOKEN
sudo systemctl enable --now monitor
```

驱动: 将官方 `waveshare_epd` 放到项目下，或保留仓库内  
`waveshare_driver/RaspberryPi_JetsonNano/python/lib`（`app.py` 已自动加入 path）。

可选环境变量:

| 变量 | 默认 | 说明 |
|------|------|------|
| `ENABLE_PLAYWRIGHT_FALLBACK` | `0` | `1` 时 REST 失败回退 Chromium |
| `USAGE_LOGIN_BACKOFF` | `3600` | Platform 登录过期后降频重试秒数 |
| `MONITOR_TOKEN` | 空 | API 鉴权 |

## Windows 部署到 Pi

```powershell
$env:PI_HOST="192.168.0.223"
$env:PI_USER="liuxfs"
$env:PI_SSH_KEY="$env:USERPROFILE\.ssh\id_rsa"   # 推荐
# 或: $env:PI_PASS="..."                         # 勿写入仓库
py -3 deploy_to_pi.py
```

首次请先 `ssh liuxfs@192.168.0.223` 接受 host key。

## Windows reporter（已停用）

Claude Code hooks 与 `windows-reporter` 默认部署路径已取消；DeepSeek 抓取与墨水屏不依赖 hooks。  
`/api/status` 仍可用，但不再要求配置 hooks。

若需手动调试（可选）:

```powershell
$env:PI_MONITOR_URL="http://192.168.0.223:5000"
$env:MONITOR_TOKEN="..."   # 若 Pi 启用了鉴权
py -3 ../windows-reporter/reporter.py running --context 42 --round 3
```

历史 hooks 示例见 `windows-reporter/2026-07-21-deepseek-usage-monitor.md`（勿再默认启用）。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 (无需 token) |
| GET | `/api/dashboard` | 完整状态 |
| POST | `/api/status` | CC 状态上报 |

若设置 `MONITOR_TOKEN`，后两个接口需要头: `X-Monitor-Token: <token>`。
