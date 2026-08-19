# 树莓派 4B → 核桃派 1B 迁移手册

> 适用项目：`deepseek-usage-monitor`（DeepSeek 用量监控 + Waveshare 3.97″ 墨水屏 + 可选 LED）  
> 编写基准：核桃派官方 Wiki（[wiki.walnutpi.com](https://wiki.walnutpi.com)）已核实事实 + 本仓库当前路径（2026-08）  
> **不要 commit 本手册中的密钥/密码示例到公开仓库；下列命令中的密钥请换成你自己的。**

---

## 目录

1. [概述与迁移目标 / 非目标](#1-概述与迁移目标--非目标)
2. [硬件与系统差异对照表](#2-硬件与系统差异对照表)
3. [迁移前准备与备份清单](#3-迁移前准备与备份清单)
4. [烧录系统](#4-烧录系统)
5. [基础系统配置](#5-基础系统配置)
6. [启用 SPI / GPIO](#6-启用-spi--gpio)
7. [部署 usage-monitor 代码与依赖](#7-部署-usage-monitor-代码与依赖)
8. [必须修改的代码 / 配置](#8-必须修改的代码--配置)
9. [墨水屏验证步骤](#9-墨水屏验证步骤)
10. [LED（可选）验证](#10-led可选验证)
11. [Flask / 健康检查与 Windows 侧](#11-flask--健康检查与-windows-侧)
12. [systemd 开机自启](#12-systemd-开机自启)
13. [完整验收清单](#13-完整验收清单)
14. [常见问题与回退到树莓派](#14-常见问题与回退到树莓派)
15. [附录](#15-附录)

---

## 1. 概述与迁移目标 / 非目标

### 1.1 一句话结论

可以把本项目迁到核桃派 1B，但**不是「插上 HAT 原样跑」**：必须换官方 Debian 镜像、改默认用户与 systemd 路径、用 `set-device` 启用 **SPI1**（`/dev/spidev1.0`）、改 Waveshare `epdconfig.py` 的总线号与板型嗅探，并接受墨水屏/gpiozero **无官方保证、需实测**。

### 1.2 迁移目标（要达成）

| 目标 | 说明 |
|------|------|
| DeepSeek 余额 + Platform 用量抓取 | Flask + `usage_scraper` + `auth_state.json` |
| Waveshare 3.97″ 墨水屏仪表盘 | `eink_dashboard.py` → `waveshare_epd` |
| systemd 开机自启 | `monitor.service` |
| （可选）双色 LED | `led_controller.py`，BCM 5/6（需实测编号） |
| 局域网 `/health`、`/api/dashboard` | 端口默认 `5000` |

### 1.3 非目标（本次不必做）

| 非目标 | 原因 |
|--------|------|
| Windows Claude Code hooks / `windows-reporter` | **已停用**；迁移可不装 Windows 侧 reporter |
| 墨水屏上的 CC 上下文%/会话$ | `SHOW_CC_CONTEXT = False`（`config.py`） |
| 官方保证 Waveshare e-Paper 兼容 | 官方未适配；可尝试但无保证 |
| 假定 gpiozero/lgpio 为核桃派官方推荐 | 官方 Python **主推 Blinka**；gpiozero/lgpio 仅「先试后回退」 |
| 树莓派 `raspi-config` / `spidev0.0` 流程 | **不适用** |

### 1.4 仓库结构（归拢后）

```
deepseek-usage-monitor/
├── README.md
├── docs/
│   ├── walnutpi-1b-migration-guide.md   ← 本手册
│   ├── 2026-07-21-deepseek-usage-monitor-design.md
│   └── 2026-07-21-deepseek-usage-monitor-plan.md
├── usage-monitor/                       ← Pi / 核桃派端主项目
│   ├── app.py
│   ├── config.py
│   ├── eink_dashboard.py
│   ├── led_controller.py
│   ├── usage_scraper.py
│   ├── weather.py
│   ├── monitor.service
│   ├── deploy_to_pi.py
│   ├── setup_pi.sh
│   ├── patch_epdconfig.py
│   ├── requirements.txt
│   └── waveshare_driver/RaspberryPi_JetsonNano/python/lib/waveshare_epd/
└── windows-reporter/                    ← 已停用（hooks/reporter 历史保留）
```

**迁移重点**：`usage-monitor/` 的 DeepSeek 用量 + 墨水屏 +（可选）LED。  
Windows 侧 reporter / hooks **可不部署**。

---

## 2. 硬件与系统差异对照表

| 项目 | 树莓派 4B（当前运行） | 核桃派 1B（目标） | 迁移影响 |
|------|----------------------|-------------------|----------|
| SoC | Broadcom BCM2711 | 全志 H616 / H618（驱动兼容） | 驱动/GPIO 库不可照搬假设 |
| 推荐系统 | Raspberry Pi OS | **核桃派 OS Debian 12**（Desktop / Server） | 必须重烧；勿默认 Ubuntu |
| 默认用户 | 本项目用 `liuxfs` | **`pi` / `pi`**；root **`root` / `root`** | systemd / 家目录全改 |
| 40 针排针 | 标准 40-pin | **尺寸/物理类似**树莓派 | 物理可插 HAT；**不保证 BCM 软件完全兼容** |
| SPI | 常用 SPI0 → `/dev/spidev0.0` | **仅 SPI1** → `/dev/spidev1.0` | **最大坑**：驱动 `SPI.open(0,0)` 必须改 |
| SPI 启用 | `raspi-config` / dtoverlay | `sudo set-device enable spidev1_0` + **重启** | 不用树莓派那套 |
| Python GPIO（官方） | gpiozero + lgpio（本项目） | **主推定制 Blinka**（`digitalio` / `board.*`） | gpiozero/lgpio **未获官方背书** |
| 墨水屏 | Waveshare 3.97″（本项目已跑通） | 官方未适配 e-Paper；有自家 3.5″ SPI LCD | **可尝试，无保证** |
| 运行目录（本仓库约定） | `/home/liuxfs/usage-monitor` | 建议 `/home/pi/usage-monitor` | 改 service / 脚本硬编码 |
| Flask | `:5000` | 同左（应用层不变） | 改 IP 即可 |

### 2.1 Waveshare 3.97″ 在树莓派上的引脚（仓库 `epdconfig.py`）

当前 RaspberryPi 分支定义（BCM 编号）：

| 信号 | BCM | 典型 40 针物理脚（树莓派惯例） |
|------|-----|-------------------------------|
| RST | 17 | 11 |
| DC | 25 | 22 |
| CS | 8 | 24 |
| BUSY | 24 | 18 |
| PWR | 18 | 12 |
| MOSI | 10 | 19 |
| SCLK | 11 | 23 |
| LED 红 / 绿 | 5 / 6 | 29 / 31 |

> ⚠️ **警告**：核桃派官方措辞是「40Pin GPIO（和树莓派类似）」，**不是**「BCM 编号软件完全兼容」。LED/控制脚请用 `gpio pins` / `import board` 对照后再定号；物理脚对齐 ≠ 软件编号对齐。

### 2.2 核桃派 SPI1 物理脚（官方）

| 功能 | 物理脚 | 备注 |
|------|--------|------|
| MOSI | 19 | SPI1 |
| MISO | 21 | SPI1 |
| SCLK | 23 | SPI1 |
| CS0 | 24 | → `spidev1_0` → `/dev/spidev1.0` |
| CS1 | 26 | `spidev1_1` |

官方文档明确：**40pin 上只有 SPI1**（不是树莓派那条 SPI0）。

---

## 3. 迁移前准备与备份清单

> ⚠️ **旧树莓派在核桃派完全验收通过前不要拆机、不要格式化 SD。** 保留可回退环境。

### 3.1 从旧 Pi 备份（在能 SSH 上旧板时执行）

```bash
# 在旧树莓派上
cd ~/usage-monitor   # 或 /home/liuxfs/usage-monitor

# 1) 认证与密钥相关（最重要）
ls -la auth_state.json
sudo systemctl cat monitor | sed -n '1,80p'

# 2) 打包关键文件到本机（在 Windows 上拉）
```

Windows PowerShell 示例（按你的旧 IP/用户改）：

```powershell
$OldHost = "192.168.0.223"
$OldUser = "liuxfs"
$BackupDir = "D:\backup\usage-monitor-pi-$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

scp "${OldUser}@${OldHost}:/home/liuxfs/usage-monitor/auth_state.json" $BackupDir\
scp "${OldUser}@${OldHost}:/etc/systemd/system/monitor.service" $BackupDir\
# 若用了 drop-in:
# scp "${OldUser}@${OldHost}:/etc/systemd/system/monitor.service.d/override.conf" $BackupDir\

# 可选：整目录同步（不含 venv，体积更小）
# scp -r "${OldUser}@${OldHost}:/home/liuxfs/usage-monitor" $BackupDir\
```

### 3.2 必须备份的清单

| 项 | 路径 / 来源 | 用途 |
|----|-------------|------|
| Platform 登录态 | `auth_state.json` | 用量抓取 cookie；丢了要重新 `login` |
| API Key | `DEEPSEEK_API_KEY`（systemd Environment / override） | 余额 API |
| 可选 Token | `MONITOR_TOKEN` | `/api/*` 鉴权 |
| 服务单元 | `monitor.service`（及 override） | 对照环境变量 |
| 网络信息 | 旧 Pi IP、Wi‑Fi SSID 密码 | 新板联网 |
| 硬件照片 | HAT/LED 接线照片 | 对照排针 |

### 3.3 检查旧板当前是否健康（基线对照）

```bash
curl -sS http://127.0.0.1:5000/health
sudo systemctl status monitor --no-pager -l | head -30
ls -l /dev/spidev*
```

记下：`eink_ready`、`led_ready`、余额是否更新。迁移后用同一套命令对比。

### 3.4 物料与工具

- 核桃派 1B 主板 + 合格 5V 电源（按官方供电建议，避免欠压）
- microSD（建议 ≥16GB，Class10 / A1+）
- 读卡器；Windows 烧录工具（如 balenaEtcher / Rufus，按官方镜像说明）
- 网线或已知可用的 Wi‑Fi
- （可选）HDMI 显示器：首次桌面初始化 / Platform 登录更方便
- G 盘镜像（见下一节）或官网下载

---

## 4. 烧录系统

### 4.1 推荐镜像（已核实）

- **推荐**：**核桃派 OS Debian 12**（教程与本手册以此为准）
- 本机 G 盘可有：

```text
G:\核桃派1B镜像下载\核桃派Debian（推荐）\2026-5-20\
  2026-5-20_V2.6.0_WalnutPi-1B_6.1.31_debian12_desktop.rar
  2026-5-20_V2.6.0_WalnutPi-1B_6.1.31_debian12_server.rar
```

| 变体 | 建议 |
|------|------|
| **server** | 无桌面、更轻；本项目以 headless + Flask 为主时优先 |
| **desktop** | 需要本机浏览器登录 DeepSeek Platform、图形调试时用 |

> 💡 Ubuntu 22.04 镜像存在于 G 盘其它目录，官方说明偏「特殊需求（如 ROS2）」——**普通用户建议 Debian**。

### 4.2 烧录步骤（概要）

1. 解压 `.rar` 得到镜像文件（`.img` 等，以压缩包内为准）。
2. 用烧录工具写入 microSD。
3. 卡插入核桃派，接电源开机。
4. **桌面版首次启动可能需数分钟初始化**，耐心等待（官方 os_intro）。

### 4.3 烧录后首检

接串口/HDMI/SSH 登录后：

```bash
cat /etc/WalnutPi-release
uname -a
whoami
hostname -I
```

期望：能看到 WalnutPi 版本信息（如 V2.6.0 一类）；当前用户为 `pi`（或你新建的用户）。

### 4.4 可选：OTA（≥ v2.0）

```bash
# 升级前务必备份；官方警告升级可能丢数据
sudo wpi-update
```

迁移验收通过前，**建议先不要急着 OTA**，避免引入变量。

---

## 5. 基础系统配置

### 5.1 默认账号（官方）

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 普通用户 | `pi` | `pi` |
| 管理员 | `root` | `root` |

> ⚠️ 内网设备也请尽快改密码；勿把密码写进仓库或本手册副本的公开处。

```bash
passwd          # 改 pi 密码
sudo passwd     # 如需改 root
```

### 5.2 SSH

```bash
# 板上确认 sshd
sudo systemctl status ssh --no-pager || sudo systemctl status sshd --no-pager

# 从 Windows 首次连接（接受 host key）
```

```powershell
ssh pi@<核桃派IP>
```

配置本机密钥（推荐，后续 `deploy_to_pi.py` 可用）：

```powershell
# 若尚无密钥
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -N '""'

type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@<核桃派IP> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

### 5.3 网络

```bash
ip -br a
ping -c 3 8.8.8.8
ping -c 3 api.deepseek.com
```

建议：给核桃派做路由器 DHCP 静态绑定（或本机 netplan/NetworkManager 静态 IP），避免 Flask URL 飘移。

### 5.4 供电与散热

- 使用稳定 5V 电源；HAT + 墨水屏刷新时瞬时电流可能升高。
- 欠压时常见症状：随机重启、SPI 花、服务被 systemd 反复拉起。
- 核对：`dmesg | grep -i -E 'under.?volt|throttl|thermal'`（若内核有相关日志）。

### 5.5 是否沿用用户名 `liuxfs`？

两种策略任选其一（推荐 A）：

| 策略 | 做法 | 优点 |
|------|------|------|
| **A. 用官方 `pi`** | 改 `monitor.service` / `setup_pi.sh` 路径到 `/home/pi/...` | 与官方文档、远程开发示例一致 |
| B. 新建 `liuxfs` | `sudo adduser liuxfs` 并加 sudo/gpio/spi 组 | 少改 service 里的用户名字符串 |

本手册后续命令以 **策略 A：`pi` + `/home/pi/usage-monitor`** 为准。

---

## 6. 启用 SPI / GPIO

### 6.1 查看当前设备状态

```bash
set-device status
gpio pin spi
gpio pins
```

说明：

- `set-device` 基于 device tree overlay；**启用后需重启**才生效（官方 gpio_config）。
- 部分驱动互斥：例如启用官方 3.5″ LCD 会占用 SPI1，就不能同时用 `spidev1.0`。

### 6.2 启用 SPI 用户态设备（必须）

```bash
# 启用 SPI1 CS0 → 重启后出现 /dev/spidev1.0
sudo set-device enable spidev1_0
sudo reboot
```

重启后验证：

```bash
ls -l /dev/spidev*
# 期望至少有: /dev/spidev1.0

# 权限：确认 pi 能访问（组名以板上为准，常见 dialout/spi）
ls -l /dev/spidev1.0
groups
# 若无权: sudo usermod -aG dialout,spi,gpio pi   # 组名以实际 ls -l 为准
# 然后重新登录 SSH
```

Python 快速探测：

```bash
python3 - <<'PY'
import os
print("spidev1.0 exists:", os.path.exists("/dev/spidev1.0"))
print("spidev0.0 exists:", os.path.exists("/dev/spidev0.0"))
try:
    import spidev
    spi = spidev.SpiDev()
    spi.open(1, 0)   # bus=1, device=0  ← 核桃派
    print("open(1,0) OK")
    spi.close()
except Exception as e:
    print("FAIL:", e)
PY
```

> 🚨 **禁止**再按树莓派习惯假设 `/dev/spidev0.0` 或 `SPI.open(0, 0)`。在核桃派上这是迁移失败的头号原因。

### 6.3 （可选）I2C

本项目墨水屏主路径是 SPI；若外设需要 I2C：

```bash
sudo set-device enable i2c1
sudo reboot
# 然后: ls /dev/i2c*
```

### 6.4 GPIO 库策略（先试后回退）

| 优先级 | 方案 | 说明 |
|--------|------|------|
| 官方主推 | **Blinka**（预装定制路径，见 Wiki `blinka_intro`） | `digitalio` / `board.*` |
| 本项目现状 | gpiozero + `GPIOZERO_PIN_FACTORY=lgpio` | **未获核桃派官方背书**；可先试 |
| 回退 | 改 `epdconfig` 用 `RPi.GPIO`/`spidev` 直控，或改写为 Blinka | LED/`led_controller.py` 同步改 |

```bash
# 探测现有库（不代表官方推荐）
python3 -c "import gpiozero; print('gpiozero', gpiozero.__version__)"
python3 -c "import lgpio; print('lgpio OK')" 2>/dev/null || echo "lgpio missing"
python3 -c "import board, digitalio; print('Blinka OK', board.__file__)" 2>/dev/null || echo "Blinka import failed"
```

---

## 7. 部署 usage-monitor 代码与依赖

### 7.1 从 Windows 上传代码

**方式一：SCP 整目录（首次推荐）**

```powershell
$PiHost = "<核桃派IP>"
$PiUser = "pi"
$Local  = "D:\pythonProject\deepseek-usage-monitor\usage-monitor"
$Remote = "/home/pi/usage-monitor"

ssh "${PiUser}@${PiHost}" "mkdir -p $Remote"
scp -r "$Local\*" "${PiUser}@${PiHost}:${Remote}/"
# 再单独传 auth（若从备份恢复）
# scp "D:\backup\...\auth_state.json" "${PiUser}@${PiHost}:${Remote}/"
```

**方式二：`deploy_to_pi.py`（增量更新）**

脚本默认：`PI_USER=liuxfs`、`PI_HOST=192.168.0.223`、项目目录 `/home/<user>/usage-monitor`。迁到核桃派时覆盖环境变量：

```powershell
cd D:\pythonProject\deepseek-usage-monitor\usage-monitor
$env:PI_HOST = "<核桃派IP>"
$env:PI_USER = "pi"
$env:PI_SSH_KEY = "$env:USERPROFILE\.ssh\id_ed25519"
# 可选: $env:PI_PROJECT_DIR = "/home/pi/usage-monitor"
py -3 deploy_to_pi.py
```

注意：`deploy_to_pi.py` 的 `FILES_TO_UPLOAD` **不含**整个 `waveshare_driver/`。首次请用 SCP 把驱动目录一并传上，或保证板上已有：

```text
/home/pi/usage-monitor/waveshare_driver/RaspberryPi_JetsonNano/python/lib/waveshare_epd/
```

`app.py` 会把上述 `lib` 与（若存在）`./waveshare_epd` 加入 `sys.path`。

### 7.2 板上创建 venv 与依赖

```bash
cd /home/pi/usage-monitor
sudo apt update
sudo apt install -y python3-venv python3-dev fonts-wqy-microhei \
  python3-spidev 2>/dev/null || true

python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 下列为「先试」项，非官方必装清单
pip install lgpio spidev 2>/dev/null || pip install spidev

# Playwright 回退默认关闭；除非设 ENABLE_PLAYWRIGHT_FALLBACK=1，否则不要装 Chromium（易吃内存）
```

检查中文字体（墨水屏标题需要）：

```bash
fc-list :lang=zh | grep -i wqy || sudo apt install -y fonts-wqy-microhei
```

### 7.3 恢复认证

```bash
# 从备份拷回
ls -la /home/pi/usage-monitor/auth_state.json

# 若无备份：需显示器/VNC/桌面浏览器登录 Platform
cd /home/pi/usage-monitor
source venv/bin/activate
python usage_scraper.py login
```

### 7.4 不要做的事

- 不要部署 / 启用 `windows-reporter` 或改用户 `~/.claude/settings.json` hooks（已停用）。
- 不要把 `DEEPSEEK_API_KEY` 写进 git 跟踪文件；用 systemd Environment / `systemctl edit`。

---

## 8. 必须修改的代码 / 配置

> 以下路径均相对于板上 `/home/pi/usage-monitor/`，或仓库 `usage-monitor/`。

### 8.1 【必须】强制 Waveshare 走 RaspberryPi 实现 + SPI1

文件：

```text
waveshare_driver/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epdconfig.py
```

#### 问题 A：板型嗅探会走错分支

文件末尾逻辑（摘要）：

```python
# cat /proc/cpuinfo | grep Raspberry
if "Raspberry" in output:
    implementation = RaspberryPi()
elif os.path.exists('/sys/bus/platform/drivers/gpio-x3'):
    implementation = SunriseX3()
else:
    implementation = JetsonNano()   # ← 核桃派无 "Raspberry" 字样时会掉进这里！
```

核桃派 `/proc/cpuinfo` **没有** `Raspberry` 字符串 → 会实例化 **JetsonNano**（依赖 `sysfs_software_spi.so` / `Jetson.GPIO`）→ **必炸**。

**改法（推荐显式强制）：** 将文件末尾板型选择改为强制 RaspberryPi，例如：

```python
# --- Walnut Pi 1B migration: force RaspberryPi path ---
# 原逻辑在非树莓派上会落到 JetsonNano，核桃派不可用。
implementation = RaspberryPi()

for func in [x for x in dir(implementation) if not x.startswith('_')]:
    setattr(sys.modules[__name__], func, getattr(implementation, func))
```

（删除或注释掉原来的 `grep Raspberry` 分支即可。）

#### 问题 B：SPI 总线号

在 `RaspberryPi.module_init` 内，原代码：

```python
# SPI device, bus = 0, device = 0
self.SPI.open(0, 0)
```

**必须改为：**

```python
# Walnut Pi 1B: 仅 SPI1 → /dev/spidev1.0
self.SPI.open(1, 0)
self.SPI.max_speed_hz = 4000000
self.SPI.mode = 0b00
```

#### 问题 C：gpiozero 可能失败

`RaspberryPi.__init__` 使用 `gpiozero.LED` / `Button`。若板上 gpiozero/lgpio 不可用：

1. **先试**：安装 `lgpio`，运行时设 `GPIOZERO_PIN_FACTORY=lgpio`（与现 `app.py` / `monitor.service` 一致）。
2. **回退**：用仓库内 `patch_epdconfig.py` 思路改为 `RPi.GPIO`（若该库在 H616 上可用），或手工改写 digital_write/read 为 Blinka/`gpiod`。
3. 不要写进文档「官方推荐 gpiozero」——**官方主推是 Blinka**。

验证嗅探结果：

```bash
cd /home/pi/usage-monitor
source venv/bin/activate
python3 - <<'PY'
import sys
sys.path.insert(0, "waveshare_driver/RaspberryPi_JetsonNano/python/lib")
from waveshare_epd import epdconfig
print("implementation class:", type(epdconfig.implementation).__name__)
# 期望: RaspberryPi
print("RST/DC/BUSY/PWR:", epdconfig.RST_PIN, epdconfig.DC_PIN, epdconfig.BUSY_PIN, epdconfig.PWR_PIN)
PY
```

### 8.2 【必须】systemd 用户与路径

当前仓库 `monitor.service`：

```ini
User=liuxfs
WorkingDirectory=/home/liuxfs/usage-monitor
Environment="GPIOZERO_PIN_FACTORY=lgpio"
Environment="DEEPSEEK_API_KEY=sk-your-key-here"
ExecStart=/home/liuxfs/usage-monitor/venv/bin/python /home/liuxfs/usage-monitor/app.py
```

核桃派建议改为（示例）：

```ini
[Unit]
Description=DeepSeek Usage Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/usage-monitor
# gpiozero 后端：先试 lgpio；若失败可去掉本行并改用其它 GPIO 方案
Environment="GPIOZERO_PIN_FACTORY=lgpio"
Environment="DEEPSEEK_API_KEY=sk-你的真实密钥"
# Environment="MONITOR_TOKEN=change-me"
# Environment="ENABLE_PLAYWRIGHT_FALLBACK=1"
ExecStart=/home/pi/usage-monitor/venv/bin/python /home/pi/usage-monitor/app.py
Restart=always
RestartSec=10
MemoryMax=512M
MemoryHigh=400M

[Install]
WantedBy=multi-user.target
```

更安全：密钥用 drop-in，不写进单元文件：

```bash
sudo systemctl edit monitor
```

```ini
[Service]
Environment="DEEPSEEK_API_KEY=sk-xxxx"
# Environment="MONITOR_TOKEN=xxxx"
```

### 8.3 【建议】修正 `setup_pi.sh` 硬编码路径

仓库脚本写死 `/home/liuxfs/usage-monitor/...`。在核桃派上请改成 `/home/pi/usage-monitor/...`，或不用该脚本、手动执行等价步骤（装字体 + `systemctl restart monitor`）。

### 8.4 【建议】`deploy_to_pi.py` 环境变量

长期迁移后，本机部署习惯改为：

```powershell
$env:PI_USER = "pi"
$env:PI_HOST = "<核桃派IP>"
```

无需改脚本默认值也可工作（环境变量优先）。

### 8.5 【确认即可】业务配置

`config.py` 关键项（迁移一般不用改逻辑）：

| 项 | 当前值 | 说明 |
|----|--------|------|
| `SHOW_CC_CONTEXT` | `False` | 不绘 CC 上下文；hooks 已停用 |
| `FLASK_PORT` | `5000` | 可按需改 |
| `LED_RED_PIN` / `LED_GREEN_PIN` | `5` / `6` | **核桃派上需实测**；不对则用环境变量覆盖 |
| `AUTH_STATE_FILE` | `./auth_state.json` | 保持权限 `600` 建议 |

```bash
# 若 LED 脚号需调整（示例）
# 在 systemd drop-in:
# Environment="LED_RED_PIN=..."
# Environment="LED_GREEN_PIN=..."
```

（需在 `config.py` 已支持的 env 名：`LED_RED_PIN` / `LED_GREEN_PIN`。）

### 8.6 修改项速查

| 优先级 | 文件 | 改什么 |
|--------|------|--------|
| P0 | `epdconfig.py` | 强制 `RaspberryPi()`；`SPI.open(1, 0)` |
| P0 | `monitor.service` | `User` / 路径 / API Key |
| P1 | GPIO 运行时 | 先试 lgpio；失败再 Blinka/直控 |
| P1 | `setup_pi.sh` | 路径 `liuxfs` → `pi` |
| P2 | LED 脚号 | 实测后改 env |
| — | `windows-reporter` | **不装** |

---

## 9. 墨水屏验证步骤

> ⚠️ 官方未适配 Waveshare 墨水屏；下列步骤用于**最小化证明链路**，失败属预期风险，请保留旧 Pi。

### 9.0 硬件检查

1. HAT 与 40 针对齐、完全插紧；必要时用螺丝固定。
2. 确认未同时启用会占用 SPI1 CS0 的官方 LCD（`set-device status`）。
3. 供电充足。

### 9.1 最小：spidev + 板型

见 [§6.2](#62-启用-spi-用户态设备必须) 与 [§8.1](#81-必须强制-waveshare-走-raspberrypi-实现--spi1) 的 Python 探测。  
`implementation class` 必须是 `RaspberryPi`，且 `open(1,0)` 成功。

### 9.2 最小清屏

```bash
cd /home/pi/usage-monitor
source venv/bin/activate
export GPIOZERO_PIN_FACTORY=lgpio   # 先试；失败再换方案

python3 - <<'PY'
import sys
sys.path.insert(0, "waveshare_driver/RaspberryPi_JetsonNano/python/lib")
from waveshare_epd import epd3in97
epd = epd3in97.EPD()
print("init...")
epd.init()
print("Clear...")
epd.Clear()
print("sleep...")
epd.sleep()
print("OK")
PY
```

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 找不到 `spidev` | 未装库 / 未启用设备 | `pip install spidev`；`set-device enable spidev1_0` + 重启 |
| `No such device` / bus 0 | 仍 `open(0,0)` | 改为 `open(1,0)` |
| `Jetson` / `.so` 缺失 | 板型嗅探走错 | 强制 `RaspberryPi()` |
| gpiozero / lgpio 异常 | 后端不兼容 | 换 Blinka 或 RPi.GPIO 式直控 |
| BUSY 超时 | 脚号/接线/供电 | 查物理连接；用 `gpio pins` 核对 |
| 全白/全黑无变化 | SPI 通但时序/CS 问题 | 降 `max_speed_hz` 试 1_000_000；确认 CS0 |

### 9.3 Dashboard 单次渲染

```bash
cd /home/pi/usage-monitor
source venv/bin/activate
export GPIOZERO_PIN_FACTORY=lgpio
export DEEPSEEK_API_KEY='sk-你的密钥'

python3 - <<'PY'
from eink_dashboard import EinkDashboard
eink = EinkDashboard()
eink.init_hardware()
state = {
    "balance": {"total_balance": "测试", "granted_balance": "-", "topped_up_balance": "-"},
    "usage": {"period_spending": "0", "total_spending": "0", "total_requests": 0,
              "total_tokens": 0, "models": []},
    "cc_status": "idle", "cc_panel": "idle",
    "weather": {}, "alerts": [], "services": {},
    "last_updated": {},
}
print(eink.render(state))
eink.sleep()
PY
```

期望：屏上出现「DEEPSEEK 用量监控」类中文标题（依赖文泉驿字体）。

### 9.4 再启完整服务

见 [§12](#12-systemd-开机自启)。服务起来后看：

```bash
curl -sS http://127.0.0.1:5000/health | python3 -m json.tool
# eink_ready 应为 true
journalctl -u monitor -n 80 --no-pager
```

---

## 10. LED（可选）验证

LED 依赖 `gpiozero`（`led_controller.py`），与墨水屏 GPIO 栈相同风险。

```bash
cd /home/pi/usage-monitor
source venv/bin/activate
export GPIOZERO_PIN_FACTORY=lgpio

python3 - <<'PY'
from led_controller import LEDController
import time
led = LEDController(red_pin=5, green_pin=6)
for s in ("idle", "running", "waiting", "error", "idle"):
    print("->", s)
    led.set_status(s)
    time.sleep(1.5)
led.cleanup()
print("OK")
PY
```

| 结果 | 行动 |
|------|------|
| 灯态正确 | 可保留；hooks 停用后多数时间停在 idle 绿灯 |
| 脚号不对 | 用官方引脚图 + 万用表/LED 测；设 `LED_RED_PIN`/`LED_GREEN_PIN` |
| gpiozero 失败 | 降级：服务可无 LED（`app.py` 会 warning 后继续）；或改写 Blinka |

**hooks/reporter 已停用**：即使 LED 硬件正常，也不会再有 Windows 侧 `running/waiting` 实时推送；不影响 DeepSeek 用量与墨水屏主功能。

---

## 11. Flask / 健康检查与 Windows 侧

### 11.1 健康检查

```bash
curl -sS http://127.0.0.1:5000/health
curl -sS http://127.0.0.1:5000/api/dashboard   # 若设置了 MONITOR_TOKEN 会 401
```

带 Token：

```bash
curl -sS -H "X-Monitor-Token: 你的token" http://127.0.0.1:5000/api/dashboard
```

`/health` 关键字段：`eink_ready`、`led_ready`、`services.deepseek_api`、`age_seconds.balance` 等。

### 11.2 Windows 浏览器 / 脚本

```powershell
$Pi = "http://<核桃派IP>:5000"
Invoke-RestMethod "$Pi/health"
# Invoke-RestMethod "$Pi/api/dashboard" -Headers @{ "X-Monitor-Token" = "..." }
```

防火墙：确保核桃派 `5000/tcp` 在局域网可达（若开了 ufw：`sudo ufw allow 5000/tcp`）。

### 11.3 Windows reporter（已停用）

- 目录：`deepseek-usage-monitor/windows-reporter/`（历史保留）。
- **迁移不必安装、不必改 Claude hooks。**
- `/api/status` 仍保留，无害；无上报时墨水屏按 idle 面板 + DeepSeek 数据工作（`SHOW_CC_CONTEXT=False`）。

若仅调试 LED/面板，可临时：

```powershell
$env:PI_MONITOR_URL = "http://<核桃派IP>:5000"
# $env:MONITOR_TOKEN = "..."
py -3 D:\pythonProject\deepseek-usage-monitor\windows-reporter\reporter.py running --context 42 --round 3
```

---

## 12. systemd 开机自启

```bash
# 单元文件已按 §8.2 改好用户/路径/密钥
sudo cp /home/pi/usage-monitor/monitor.service /etc/systemd/system/monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now monitor
sleep 3
sudo systemctl status monitor --no-pager -l | head -40
curl -sS http://127.0.0.1:5000/health
```

常用运维：

```bash
sudo systemctl restart monitor
journalctl -u monitor -f
sudo systemctl disable --now monitor   # 停用
```

内存：单元已设 `MemoryMax=512M`。核桃派内存可能小于 Pi 4B 的 4/8GB——**保持 Playwright 关闭**，避免 Chromium OOM。

---

## 13. 完整验收清单

逐项打勾：

### 系统

- [ ] `cat /etc/WalnutPi-release` 为 Debian 系核桃派 OS（建议 V2.6.0 附近）
- [ ] 能用 `pi` SSH 登录；密码已修改
- [ ] 网络稳定，`ping api.deepseek.com` 通
- [ ] `ls /dev/spidev1.0` 存在（**不是**只盯着 `spidev0.0`）

### 代码与配置

- [ ] 代码在 `/home/pi/usage-monitor`
- [ ] `epdconfig` 强制 `RaspberryPi` 且 `SPI.open(1, 0)`
- [ ] `auth_state.json` 已就位或重新 login
- [ ] systemd 使用 `User=pi` 与正确 venv 路径
- [ ] `DEEPSEEK_API_KEY` 已注入（非仓库占位符）

### 功能

- [ ] 最小清屏成功
- [ ] `/health` 返回 `status=ok`，`eink_ready=true`
- [ ] 墨水屏显示中文标题与余额/用量（数分钟内刷新）
- [ ] （可选）LED 脚号正确
- [ ] 重启后 `systemctl is-enabled monitor` 为 enabled，服务自启
- [ ] Windows 浏览器能打开 `http://<IP>:5000/health`

### 明确未做（可接受）

- [ ] 未安装 windows-reporter / 未恢复 hooks
- [ ] `SHOW_CC_CONTEXT` 仍为 `False`

---

## 14. 常见问题与回退到树莓派

### 14.1 FAQ

**Q: 为什么一跑墨水屏就找 Jetson 的 `.so`？**  
A: `epdconfig.py` 用 `grep Raspberry` 嗅探；核桃派不匹配 → `JetsonNano()`。强制 `RaspberryPi()`。

**Q: `SPI.open(0,0)` 在树莓派正常，核桃派失败？**  
A: 官方仅 SPI1，节点是 `/dev/spidev1.0`。改为 `open(1, 0)`。

**Q: `set-device enable spidev1_0` 后没有设备？**  
A: 是否**重启**？`set-device status` 是否为 enable？是否与官方 LCD 驱动互斥？

**Q: gpiozero 报错 / LED 起不来？**  
A: 官方主推 Blinka，gpiozero/lgpio 未背书。可先装 lgpio 试验；失败则禁用 LED（服务仍可跑）或改写 GPIO 后端。

**Q: 余额有、用量没有？**  
A: 检查 `auth_state.json` 与 `journalctl -u monitor`；可能需 `python usage_scraper.py login`。Playwright 默认关，勿在内存紧张时强开。

**Q: 中文方框？**  
A: `sudo apt install -y fonts-wqy-microhei`，确认 `fc-list` 能看到 wqy。

**Q: 服务不断重启？**  
A: `journalctl -u monitor -b`；常见为 GPIO/SPI 初始化异常。可临时让墨水屏失败走 mock（`app.py` 已有降级逻辑），先保证 API。

### 14.2 回退到树莓派

1. 核桃派：`sudo systemctl disable --now monitor`
2. 断电，拆 HAT，装回树莓派（旧 SD 未动则直接开机）。
3. 确认旧服务：

```bash
sudo systemctl enable --now monitor
curl -sS http://127.0.0.1:5000/health
```

4. Windows 侧若曾改监控 URL，改回旧 Pi IP。
5. 将核桃派上改过的 `epdconfig.py` **不要**未经判断同步回树莓派：  
   - 树莓派需要 `SPI.open(0, 0)` + 正常的 Raspberry 嗅探；  
   - 建议用 git 分支或文件副本区分 `epdconfig.raspberrypi.py` / `epdconfig.walnutpi.py`。

### 14.3 建议的并行策略

| 阶段 | 树莓派 | 核桃派 |
|------|--------|--------|
| 烧录 / SPI / 清屏实验 | 保持生产运行 | 实验 |
| Flask + 墨水屏稳定 24h | 热备 | 切流量（改 Windows 书签/URL） |
| 确认无回退需求 | 可归档 SD 镜像后再拆 | 生产 |

---

## 15. 附录

### 15.1 官方文档链接（已核实入口）

| 主题 | URL |
|------|-----|
| Wiki 首页 | https://wiki.walnutpi.com |
| 产品站 | https://www.walnutpi.com |
| 文档源码 | https://github.com/walnutpi/walnutpi_wiki |
| 镜像下载 | https://wiki.walnutpi.com/docs/walnutpi_1/intro/download |
| 系统简介 / 默认账号 | https://wiki.walnutpi.com/docs/walnutpi_1/os_software/os_intro |
| 硬件详解 | https://wiki.walnutpi.com/docs/walnutpi_1/getting_start/hw-detail |
| GPIO 介绍 / 引脚图 | https://wiki.walnutpi.com/docs/walnutpi_1/gpio/gpio_intro |
| set-device | https://wiki.walnutpi.com/docs/walnutpi_1/gpio/gpio_config |
| SPI（spidev1.0） | https://wiki.walnutpi.com/docs/walnutpi_1/c/spi/ |
| Blinka | https://wiki.walnutpi.com/docs/walnutpi_1/python/blinka_intro |
| 官方 3.5″ SPI LCD | https://wiki.walnutpi.com/docs/walnutpi_1/os_software/3.5_LCD |
| 论坛 | https://forum.walnutpi.com |

### 15.2 本仓库相关路径

| 路径 | 说明 |
|------|------|
| `deepseek-usage-monitor/usage-monitor/` | 板端主项目 |
| `.../monitor.service` | systemd 单元（现默认 `liuxfs`） |
| `.../deploy_to_pi.py` | Windows → 板 SFTP 部署 |
| `.../setup_pi.sh` | 字体 + 重启（路径硬编码 `liuxfs`） |
| `.../config.py` | `SHOW_CC_CONTEXT=False`、LED 脚、端口 |
| `.../eink_dashboard.py` | 墨水屏渲染 |
| `.../led_controller.py` | gpiozero LED |
| `.../app.py` | Flask；默认 `GPIOZERO_PIN_FACTORY=lgpio` |
| `.../waveshare_driver/.../epdconfig.py` | **迁移必改** |
| `.../patch_epdconfig.py` | gpiozero→RPi.GPIO 补丁思路（备选） |
| `deepseek-usage-monitor/windows-reporter/` | **已停用** |
| `deepseek-usage-monitor/docs/walnutpi-1b-migration-guide.md` | 本手册 |

### 15.3 G 盘镜像路径（本机）

```text
G:\核桃派1B镜像下载\核桃派Debian（推荐）\2026-5-20\
  …_debian12_desktop.rar
  …_debian12_server.rar
```

版本：V2.6.0，内核 6.1.31（以文件名为准）。

### 15.4 关键命令速查

```bash
# 系统
cat /etc/WalnutPi-release
sudo wpi-update          # 慎用，先备份

# SPI
set-device status
sudo set-device enable spidev1_0 && sudo reboot
ls -l /dev/spidev1.0
gpio pin spi

# 服务
sudo systemctl status monitor --no-pager -l
journalctl -u monitor -f
curl -sS http://127.0.0.1:5000/health
```

```powershell
# Windows 部署
cd D:\pythonProject\deepseek-usage-monitor\usage-monitor
$env:PI_HOST=" <IP> "; $env:PI_USER="pi"
$env:PI_SSH_KEY="$env:USERPROFILE\.ssh\id_ed25519"
py -3 deploy_to_pi.py
```

### 15.5 风险摘要（请仔细阅读）

1. **SPI 总线**：树莓派 `spidev0.0` ≠ 核桃派 `spidev1.0`。  
2. **板型嗅探**：不强制 `RaspberryPi` 会误入 Jetson 分支。  
3. **BCM 兼容**：40 针物理类似 ≠ 软件 BCM 保证兼容。  
4. **GPIO 库**：官方 Blinka；gpiozero/lgpio 仅试验。  
5. **墨水屏**：官方未适配 Waveshare e-Paper，可能最终无法稳定使用。  
6. **旧 Pi**：验收完成前保持可回退。  
7. **密钥**：勿提交 `auth_state.json` / API Key 到 git。

---

*手册结束。若官方 Wiki 更新了 `set-device` 设备名或默认账号，以 [wiki.walnutpi.com](https://wiki.walnutpi.com) 原文为准，并回改本手册对应章节。*
