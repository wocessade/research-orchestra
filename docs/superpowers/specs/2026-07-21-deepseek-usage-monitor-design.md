# DeepSeek 用量监控小屏 — 设计文档 (v2)

> 状态: 待实现 | 日期: 2026-07-21 | 修订: 墨水屏 + hooks 详细设计

## 1. 概述

树莓派 + 黑白墨水屏 + GPIO LED 搭建独立运行的 DeepSeek API 用量监控仪表盘。
通过 Claude Code hooks 实时上报运行状态，实体 LED 显示状态颜色，墨水屏展示数据面板。

### 1.1 硬件

| 组件 | 型号 | 用途 |
|------|------|------|
| 树莓派 | 3B+ 或更新 | 主控 |
| 墨水屏 | **Waveshare 5.83" (648×480)** 黑白 | 数据面板 |
| LED | 红色+绿色 各1颗 (或 RGB LED) | 状态指示灯 |
| 电阻 | 220Ω × 2 | LED 限流 |
| 外壳 | 3D 打印或淘宝成品壳 | 一体外观 |

### 1.2 核心功能

| 功能 | 说明 |
|------|------|
| 余额展示 | 充值余额、预警状态，墨水屏大字显示 |
| 消费展示 | 本期消费、累计消费、较上次变动 |
| 用量展示 | API 请求次数、Tokens 总量 |
| 模型拆分 | 各模型的请求次数和 Tokens 占比 |
| 上下文窗口 | 当前会话上下文使用率进度条，接近 compact 阈值时警告 |
| 会话信息 | 会话时长计时器、当前轮次、会话 Token 消耗 |
| 状态指示灯 | GPIO LED：绿(空闲)、黄(运行中)、黄闪(等待用户)、红(故障) |
| 余额预警 | 余额低于阈值时墨水屏版面醒目提示 |
| 自动分层刷新 | 余额 60s、用量 5min、CC 状态事件驱动 |

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────┐
│  Windows 本机                                            │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Claude Code (hooks → reporter.py)               │   │
│  │                                                 │   │
│  │  SessionStart  → "idle"                         │   │
│  │  PreToolUse    → "running"                      │   │
│  │  PostToolBatch → "running" (仍在工具循环中)      │   │
│  │  Stop          → "idle"                          │   │
│  │  StopFailure   → "error"                        │   │
│  │  Notification  → "waiting" (permission_prompt /  │   │
│  │                        elicitation_dialog)       │   │
│  │  PreCompact    → 发送上下文紧缩前状态             │   │
│  │  PostCompact   → 更新上下文百分比                 │   │
│  │  SessionEnd    → "idle" (cleanup)               │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │  HTTP POST (局域网)               │
│  ┌──────────────────┴──────────────────────────────┐   │
│  │  windows-reporter/reporter.py                    │   │
│  │  ├─ POST /api/status      → CC 状态              │   │
│  │  └─ POST /api/session     → 会话信息 (可选)      │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           │  WiFi / 局域网
┌──────────────────────────┴──────────────────────────────┐
│  树莓派 (墨水屏一体机)                                    │
│                                                         │
│  ┌───────────────────────────────────────────────┐     │
│  │  Python App (Flask + APScheduler)              │     │
│  │                                               │     │
│  │  ┌─ 数据采集 ─────────────────────────────┐   │     │
│  │  │ ① DeepSeek Balance API  每 60s         │   │     │
│  │  │ ② DeepSeek Usage Scraper 每 5min       │   │     │
│  │  │ ③ Windows CC 状态上报  事件驱动         │   │     │
│  │  └────────────────────────────────────────┘   │     │
│  │                                               │     │
│  │  ┌─ 渲染引擎 (PIL/Pillow) ────────────────┐   │     │
│  │  │ ④ DashboardRenderer: 数据 → 灰度位图    │   │     │
│  │  │ ⑤ 分层刷新策略: 局刷/全刷/不刷         │   │     │
│  │  └────────────────────────────────────────┘   │     │
│  │                                               │     │
│  │  ┌─ 硬件控制 ─────────────────────────────┐   │     │
│  │  │ ⑥ E-ink Driver (waveshare_epd / SPI)   │   │     │
│  │  │ ⑦ LED Controller (gpiozero)             │   │     │
│  │  └────────────────────────────────────────┘   │     │
│  └───────────────────────────────────────────────┘     │
│                                                         │
│  ┌──────┐    ┌──────────────────────┐                  │
│  │ LED  │    │  墨水屏 5.83"        │                  │
│  │🟢🟡🔴│    │  648×480 灰度        │                  │
│  └──────┘    └──────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Claude Code Hooks 详细设计

### 3.1 可用 Hook 事件全景

Claude Code 提供 29 个 hook 事件。下表列出与本项目相关的事件：

| Hook 事件 | 触发时机 | 本项目用途 |
|-----------|---------|-----------|
| `SessionStart` | 会话开始/恢复 | 上报 `idle`，初始化会话计时器 |
| `PreToolUse` | 工具调用执行前 | 上报 `running` |
| `PostToolBatch` | 一批并行工具调用完成后 | 维持 `running` 状态 |
| `Stop` | Claude 完成响应 | 上报 `idle` |
| `StopFailure` | 因 API 错误停止 | 上报 `error`，发送错误类型 |
| `Notification` | 系统通知 | 检测 `permission_prompt` / `elicitation_dialog` → `waiting` |
| `PreCompact` | 上下文压缩前 | 上报压缩前状态，更新上下文使用率 |
| `PostCompact` | 上下文压缩后 | 上报 `running`，重置上下文百分比 |
| `SessionEnd` | 会话终止 | 上报 `idle`，清理 |

### 3.2 状态转换图

```
                    ┌─────────┐
         SessionStart │         │ Stop / SessionEnd
        ─────────────→│  IDLE   │←────────────────
                       │  🟢     │
                       └────┬────┘
                            │ PreToolUse / PostToolBatch
                            ▼
                       ┌─────────┐
                       │ RUNNING │
                       │  🟡     │──────┐
                       └────┬────┘      │
                            │           │ StopFailure
                            │           ▼
              Notification  │      ┌─────────┐
          (permission_prompt│      │  ERROR  │
           /elicitation)    │      │  🔴     │
                            ▼      └────┬────┘
                       ┌─────────┐      │
                       │ WAITING │      │ (任意 hook)
                       │  🟡💡    │──────┘
                       └────┬────┘  回 idle
                            │
                  (用户操作后回到 running)
```

### 3.3 Hook 配置 (settings.json)

```jsonc
// ~/.claude/settings.json 或 .claude/settings.local.json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "idle", "--session-start"],
            "timeout": 10
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "running"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "PostToolBatch": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "running"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "idle"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "StopFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "error"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt|elicitation_dialog",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "waiting"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "compact-warning"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "running"],
            "timeout": 5,
            "async": true
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["D:/pythonProject/windows-reporter/reporter.py", "idle", "--session-end"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### 3.4 reporter.py 详细设计

```python
"""
CC Hooks 状态上报脚本。
被 hooks 调用，将 CC 运行状态通过 HTTP POST 发送到树莓派。

用法:
  python reporter.py <status> [flags]

状态值:
  idle            - CC 空闲
  running         - CC 运行中（工具调用或模型推理）
  waiting         - CC 等待用户操作（权限确认/MCP elicitation）
  error           - API 错误
  compact-warning - 上下文即将压缩
"""

import requests
import sys
import os
import json
import time

PI_URL = os.getenv("PI_MONITOR_URL", "http://raspberrypi.local:5000")

def report(payload: dict, timeout: int = 5):
    try:
        requests.post(f"{PI_URL}/api/status", json=payload, timeout=timeout)
    except Exception:
        pass  # 静默失败，不影响 CC 正常运行

if __name__ == "__main__":
    status = sys.argv[1] if len(sys.argv) > 1 else "idle"

    payload = {
        "status": status,
        "timestamp": time.time(),
        "host": os.getenv("COMPUTERNAME", "unknown"),
        "session_id": os.getenv("CLAUDE_SESSION_ID", ""),  # 如果 CC 传入
    }

    report(payload)
```

---

## 4. 墨水屏渲染设计

### 4.1 刷新策略

墨水屏有残影问题，需要分层管理刷新：

| 刷新级别 | 触发条件 | 方式 | 耗时 | 频率 |
|----------|---------|------|------|------|
| ⚡ **局刷** | CC 状态变化、时间更新 | 只刷新状态区域 ~50×50px | ~0.3s | 事件驱动 |
| 🔄 **全刷** | 余额/用量数据变化 | 整屏刷新 + 清残影 | ~3s | 数据变更时 |
| 🔄 **全刷(强制)** | 每 30 分钟定期清残影 | 整屏全刷 | ~3s | 30min |
| 🛑 **不刷** | 无数据变化 | 保持画面 | — | — |

### 4.2 墨水屏驱动

使用 Waveshare 官方 Python 库：

```python
# 依赖
# pip install waveshare-epd  # 或从 GitHub clone 官方 demo 代码

from waveshare_epd import epd5in83_V2  # 5.83寸
from PIL import Image, ImageDraw, ImageFont

class EinkDashboard:
    def __init__(self):
        self.epd = epd5in83_V2.EPD()
        self.epd.init()
        self.last_data_hash = None

    def render(self, data: dict) -> str:
        """渲染仪表盘到位图，返回刷新方式 'partial'|'full'|'none'"""
        new_hash = hash(json.dumps(data, sort_keys=True))
        if new_hash == self.last_data_hash:
            return "none"

        # PIL 渲染 648×480 灰度位图
        image = Image.new("1", (648, 480), 1)  # 1-bit 黑白
        draw = ImageDraw.Draw(image)
        # ... 绘制仪表盘 ...

        if self.last_data_hash is None or self._major_data_changed(data):
            self.epd.display(self.epd.getbuffer(image))  # 全刷
            result = "full"
        else:
            self.epd.displayPartial(self.epd.getbuffer(image))  # 局刷
            result = "partial"

        self.last_data_hash = new_hash
        return result

    def _major_data_changed(self, data: dict) -> bool:
        """判断是否需要全刷（余额变化/用量变化等）"""
        # 比较关键字段
        return True  # 简化：数据变化默认全刷
```

### 4.3 墨水屏版面布局 (648×480)

```
┌────────────────────────────────────────────────┐
│  ╔══════════════════════════════════════════╗   │ y=0
│  ║  DEEPSEEK 用量监控     ◉ 运行中  14:32  ║   │ y=30  标题栏
│  ╚══════════════════════════════════════════╝   │
│                                                 │
│  ┌──────────────────┐ ┌────────────────────┐   │
│  │  充值余额         │ │  本期消费            │   │ y=50
│  │                  │ │                    │   │
│  │  ¥ 16.58        │ │  ¥ 79.41   +2.30↗  │   │ y=90  卡片行1
│  │  预警已开启 ✓    │ │                     │   │
│  └──────────────────┘ └────────────────────┘   │
│  ┌──────────────────┐ ┌────────────────────┐   │
│  │  累计消费         │ │  API 请求次数       │   │ y=140
│  │  ¥ 203.41        │ │  6,738              │   │ y=180 卡片行2
│  └──────────────────┘ └────────────────────┘   │
│  ┌──────────────────────────────────────────┐  │
│  │  上下文窗口  ████████████░░░░░  82% 697K│  │ y=220 上下文
│  │  Compact 阈值: 850K   会话: 23min 第3轮  │  │ y=245
│  └──────────────────────────────────────────┘  │
│  ───────────────────────────────────────────── │
│  模型用量                            Tokens    │
│  ████████████░░░░ v4-flash  2,840次  221M     │ y=280
│  ████████████████ v4-pro    3,898次  297M     │ y=310
│  ───────────────────────────────────────────── │
│  ┌──────────────────────┐ ┌─────────────────┐ │
│  │ 前次更新: 2分钟前     │ │ 网络: DeepSeek  │ │ y=380
│  │ 今日会话费用: ¥3.82   │ │ 延迟 32ms      │ │ y=410 底栏
│  └──────────────────────┘ └─────────────────┘ │
│  ┌──────────────────────────────────────────┐  │
│  │ 服务: DS🟢 Zotero🟢 GitHub🟢 代理🟢 │  │ y=440 服务健康
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

### 4.4 灰度设计原则

墨水屏只有黑/白/灰（用抖动模拟灰），状态区分靠形状而非颜色：

| 信息层级 | 灰度 | 用途 |
|---------|------|------|
| 纯黑 ██ | 100% | 主要数字（余额金额）、标题 |
| 深灰 ▓▓ | 70% 抖动 | 卡片背景、进度条填充 |
| 中灰 ░░ | 40% 抖动 | 分隔线、次要文字、进度条背景 |
| 浅灰 ░░ | 15% 抖动 | 卡片边框 |
| 纯白 | 0% | 底色 |

状态图标不靠颜色：

| CC 状态 | 显示符号 |
|---------|---------|
| idle | `◉` 空心圆 (或在 LED 上绿色) |
| running | `◉` 实心圆 |
| waiting | `◉?` 实心圆 + 问号 |
| error | `⊗` X 符号 |

---

## 5. 组件设计

### 5.1 树莓派后端

**文件:** `usage-monitor/app.py`

```python
"""
Flask 主入口 — 墨水屏仪表盘后端
端口: 5000
"""

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from led_controller import LEDController
from eink_dashboard import EinkDashboard
from usage_scraper import fetch_usage
import requests
import os

app = Flask(__name__)

# 全局状态
state = {
    "balance": {},
    "usage": {},
    "cc_status": "idle",
    "cc_session_start": None,
    "cc_context_percent": 0,
    "cc_round": 0,
    "last_updated": {},
    "alerts": [],
    "network_latency_ms": 0,
}

# 硬件控制器
led = LEDController()
eink = EinkDashboard()

# DeepSeek API Key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BALANCE_URL = "https://api.deepseek.com/user/balance"


def fetch_balance():
    """每 60s 获取余额"""
    try:
        resp = requests.get(
            BALANCE_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            timeout=10
        )
        data = resp.json()
        state["balance"] = {
            "total": data["balance_infos"][0]["total_balance"],
            "currency": data["balance_infos"][0]["currency"],
            "granted": data["balance_infos"][0]["granted_balance"],
            "topped_up": data["balance_infos"][0]["topped_up_balance"],
            "is_available": data["is_available"],
        }
        state["last_updated"]["balance"] = time.time()

        # 余额预警
        total = float(state["balance"]["total"])
        if total < 5.0:
            state["alerts"] = [{"level": "warning", "message": f"余额仅剩 ¥{total}"}]
        elif total < 10.0:
            state["alerts"] = [{"level": "info", "message": f"余额低于 ¥10"}]
        else:
            state["alerts"] = []
    except Exception as e:
        print(f"Balance fetch error: {e}")


def update_eink():
    """触发墨水屏刷新"""
    result = eink.render(state)
    if result != "none":
        print(f"E-ink updated: {result}")


# 定时任务
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_balance, "interval", seconds=60)
scheduler.add_job(lambda: fetch_usage(state), "interval", minutes=5)
scheduler.add_job(update_eink, "interval", seconds=30)  # 检查是否需要刷新


@app.route("/api/dashboard")
def dashboard():
    return jsonify(state)


@app.route("/api/status", methods=["POST"])
def update_status():
    data = request.get_json()
    new_status = data.get("status", "idle")

    if state["cc_status"] != new_status:
        state["cc_status"] = new_status
        led.set_status(new_status)
        update_eink()

    if data.get("session_start"):
        state["cc_session_start"] = time.time()
        state["cc_round"] = 0

    if data.get("session_end"):
        state["cc_session_start"] = None

    return jsonify({"ok": True})


if __name__ == "__main__":
    scheduler.start()
    fetch_balance()  # 启动时立即获取
    led.set_status("idle")
    app.run(host="0.0.0.0", port=5000, debug=False)
```

### 5.2 API 设计

```
GET /api/dashboard
Response:
{
  "balance": {
    "total": "16.58", "currency": "CNY",
    "granted": "6.58", "topped_up": "10.00",
    "is_available": true
  },
  "usage": {
    "period_spending": "79.41", "total_spending": "203.41",
    "total_requests": 6738, "total_tokens": 518230239,
    "models": [
      { "name": "deepseek-v4-flash", "requests": 2840, "tokens": 221051931 },
      { "name": "deepseek-v4-pro",   "requests": 3898, "tokens": 297178308 }
    ]
  },
  "cc_status": "idle",
  "cc_session_start": 1721548800.0,  // unix timestamp or null
  "cc_context_percent": 82,          // 上下文使用率 0-100
  "cc_round": 3,                     // 当前轮次
  "last_updated": { "balance": 1721548800.0, "usage": 1721548800.0 },
  "alerts": [],
  "network_latency_ms": 32,
  "services": {
    "deepseek_api": "up",
    "zotero": "unknown",
    "github": "up"
  }
}

POST /api/status
Body: { "status": "idle|running|waiting|error|compact-warning",
        "timestamp": 1721548800.0,
        "host": "DESKTOP-XXX",
        "session_id": "..." }
Response: { "ok": true }
```

### 5.3 LED 控制器

同之前设计，不变。

### 5.4 墨水屏渲染器

**文件:** `usage-monitor/eink_dashboard.py`

核心职责：
- 接收 `state` dict → PIL `Image` 位图 → SPI 推送到墨水屏
- 维护数据 hash 判断是否需要刷新
- 区分全刷/局刷

依赖：`Pillow`、`waveshare_epd`

### 5.5 Playwright 用量抓取

同之前设计，`usage-monitor/usage_scraper.py`

---

## 6. 项目文件结构

```
D:/pythonProject/
├── usage-monitor/                  # 树莓派端代码 (部署在 Pi 上)
│   ├── app.py                      # Flask 主入口 + 定时任务
│   ├── eink_dashboard.py           # 墨水屏渲染引擎 (PIL)
│   ├── led_controller.py           # GPIO LED 控制
│   ├── usage_scraper.py            # Playwright 用量抓取
│   ├── monitor.service             # systemd 配置
│   ├── static/                     # (保留，可选 Web 调试页)
│   ├── auth_state.json             # DeepSeek 登录态 (gitignore)
│   └── requirements.txt            # Python 依赖
├── windows-reporter/               # Windows 端 (在主机上运行)
│   └── reporter.py                 # CC hooks 状态上报脚本
└── docs/superpowers/specs/
    └── 2026-07-21-deepseek-usage-monitor-design.md
```

---

## 7. 实施计划

| 阶段 | 内容 | 产出 |
|------|------|------|
| P0 | 树莓派环境搭建：RPi OS、Python、SPI 启用、墨水屏驱动测试 | 墨水屏亮起 |
| P1 | DeepSeek 余额 API + 墨水屏基础渲染（余额卡片） | 余额显示 |
| P2 | LED 接线 + GPIO 控制逻辑 | LED 可控 |
| P3 | CC hooks 配置 + reporter.py | 状态自动上报 |
| P4 | Playwright 用量抓取 + 完整仪表盘渲染 | 全功能面板 |
| P5 | 上下文窗口进度条 + 会话信息 | 增强功能 |
| P6 | 分层刷新策略调优 + 定期清残影 | 显示质量 |
| P7 | systemd 开机自启 | 上电即用 |
| P8 | 联调测试 | 全部跑通 |

---

## 8. 前提依赖

- [ ] 树莓派 (3B+ 或更新) + Raspberry Pi OS (Bookworm)
- [ ] Waveshare 5.83" 黑白墨水屏 (648×480) + HAT
- [ ] 红色 LED × 1 + 绿色 LED × 1 + 220Ω 电阻 × 2 + 杜邦线
- [ ] 3D 打印外壳 (可选)
- [ ] DeepSeek API Key (platform.deepseek.com → API Keys)
- [ ] 树莓派与 Windows 主机同一局域网
- [ ] Python 3.9+ + Flask + Pillow + gpiozero + requests + playwright
