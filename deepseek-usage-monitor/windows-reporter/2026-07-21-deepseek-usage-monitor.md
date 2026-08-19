# DeepSeek 用量监控小屏 — 实施计划

> **2026-08：CC hooks / windows-reporter 已停用**，勿再按下文「合并 hooks 到 settings.json」步骤启用。历史计划仅作参考。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在树莓派上部署一个墨水屏仪表盘，显示 DeepSeek API 用量和 Claude Code 运行状态

**Architecture:** Windows 端通过 CC hooks 上报状态到树莓派 Flask 后端；树莓派定时拉取 DeepSeek API 余额和用量；PIL 渲染灰度位图推送到 5.83" 墨水屏；GPIO 双色 LED 指示 CC 状态

**Tech Stack:** Python 3.9+, Flask, Pillow, gpiozero, requests, Playwright, APScheduler, waveshare_epd

## Global Constraints

- 墨水屏: Waveshare 5.83" (V2), 648×480, SPI 接口, 黑白
- LED: GPIO BCM 17=红, GPIO BCM 27=绿
- 树莓派 IP: 需配置到 Windows reporter 脚本
- DeepSeek API Key: 环境变量 `DEEPSEEK_API_KEY`
- Python >= 3.9
- 树莓派系统: Raspberry Pi OS (Bookworm)

---

### Task 1: 项目骨架 + 依赖清单

**Files:**
- Create: `usage-monitor/requirements.txt`
- Create: `usage-monitor/config.py`
- Create: `windows-reporter/reporter.py` (骨架)

**Produces:** 项目结构就绪，依赖清单明确

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p D:/pythonProject/deepseek-usage-monitor/usage-monitor
mkdir -p D:/pythonProject/deepseek-usage-monitor/windows-reporter
```

- [ ] **Step 2: 写入 requirements.txt**

```python
# usage-monitor/requirements.txt
flask==3.1.0
Pillow==11.1.0
gpiozero==2.0.1
requests==2.32.3
apscheduler==3.11.0
```

> Playwright 在树莓派上单独安装: `pip install playwright && playwright install chromium`

- [ ] **Step 3: 写入 config.py**

```python
# usage-monitor/config.py
import os

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
DEEPSEEK_PLATFORM_URL = "https://platform.deepseek.com"
DEEPSEEK_USAGE_URL = "https://platform.deepseek.com/usage"

# Flask
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# 刷新间隔 (秒)
BALANCE_INTERVAL = 60       # 余额 API
USAGE_SCRAPE_INTERVAL = 300 # 用量抓取
EINK_CHECK_INTERVAL = 30    # 墨水屏检查
EINK_FORCE_FULL_REFRESH = 1800  # 每30分钟强制全刷清残影

# 余额预警阈值 (CNY)
BALANCE_WARN_THRESHOLD = 10.0
BALANCE_CRITICAL_THRESHOLD = 5.0

# 上下文窗口
COMPACT_THRESHOLD_TOKENS = 850000  # 对齐 CLAUDE_CODE_AUTO_COMPACT_WINDOW

# GPIO (BCM)
LED_RED_PIN = 17
LED_GREEN_PIN = 27

# 墨水屏
EINK_WIDTH = 648
EINK_HEIGHT = 480

# 认证文件路径
AUTH_STATE_FILE = os.path.join(os.path.dirname(__file__), "auth_state.json")
```

- [ ] **Step 4: Commit**

```bash
git add usage-monitor/ windows-reporter/
git commit -m "feat: add project skeleton and config for usage monitor"
```

---

### Task 2: LED 控制器

**Files:**
- Create: `usage-monitor/led_controller.py`

**Produces:** `LEDController` 类，接受 status 字符串控制 GPIO LED

- [ ] **Step 1: 写入 LED 控制器**

```python
# usage-monitor/led_controller.py
"""GPIO LED 控制器 — 双色 LED 指示 CC 状态"""

from gpiozero import LED
from threading import Thread, Event


class LEDController:
    """控制两颗 GPIO LED:
    - 红 (BCM 17) + 绿 (BCM 27) 同时亮 = 黄色
    - 绿灯常亮 = idle
    - 黄灯常亮 = running
    - 黄灯 500ms 闪烁 = waiting
    - 红灯常亮 = error
    """

    def __init__(self, red_pin: int = 17, green_pin: int = 27):
        self.red = LED(red_pin)
        self.green = LED(green_pin)
        self._blink_thread: Thread | None = None
        self._stop_blink = Event()
        self._current_status = "idle"

    def set_status(self, status: str) -> None:
        """设置状态: idle | running | waiting | error"""
        if status == self._current_status:
            return
        self._current_status = status
        self._stop_blinking()
        self._all_off()

        if status == "idle":
            self.green.on()
        elif status == "running":
            self.red.on()
            self.green.on()  # red + green = yellow
        elif status == "waiting":
            self._start_blinking()
        elif status == "error":
            self.red.on()

    def _start_blinking(self) -> None:
        self._stop_blink.clear()
        self._blink_thread = Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    def _blink_loop(self) -> None:
        while not self._stop_blink.is_set():
            self.red.on()
            self.green.on()
            self._stop_blink.wait(0.5)
            self._all_off()
            self._stop_blink.wait(0.5)

    def _stop_blinking(self) -> None:
        if self._blink_thread and self._blink_thread.is_alive():
            self._stop_blink.set()
            self._blink_thread.join(timeout=1)

    def _all_off(self) -> None:
        self.red.off()
        self.green.off()

    def cleanup(self) -> None:
        """程序退出时清理 GPIO"""
        self._stop_blinking()
        self._all_off()
        self.red.close()
        self.green.close()
```

- [ ] **Step 2: Commit**

```bash
git add usage-monitor/led_controller.py
git commit -m "feat: add GPIO LED controller for dual-color status light"
```

---

### Task 3: 墨水屏渲染引擎

**Files:**
- Create: `usage-monitor/eink_dashboard.py`

**Produces:** `EinkDashboard` 类，接收 state dict → PIL Image → SPI 推屏，分层刷新

- [ ] **Step 1: 写入渲染引擎**

```python
# usage-monitor/eink_dashboard.py
"""墨水屏渲染引擎 — 数据 → PIL 灰度位图 → SPI 推送到 Waveshare 5.83" """

import json
import time
import hashlib
from PIL import Image, ImageDraw, ImageFont
from config import (
    EINK_WIDTH, EINK_HEIGHT, EINK_FORCE_FULL_REFRESH,
    BALANCE_WARN_THRESHOLD, BALANCE_CRITICAL_THRESHOLD,
    COMPACT_THRESHOLD_TOKENS,
)


class EinkDashboard:
    """管理墨水屏渲染和刷新策略"""

    def __init__(self):
        self.epd = None          # 延迟初始化，允许在没有硬件时测试渲染逻辑
        self.last_data_hash = ""
        self.last_full_refresh = 0.0
        self.width = EINK_WIDTH
        self.height = EINK_HEIGHT

        # 字体 (树莓派路径)
        try:
            self.font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            self.font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except OSError:
            self.font_title = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_normal = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def init_hardware(self) -> None:
        """初始化墨水屏 (需要实际硬件)"""
        from waveshare_epd import epd5in83_V2
        self.epd = epd5in83_V2.EPD()
        self.epd.init()

    def render(self, state: dict) -> str:
        """
        渲染仪表盘，返回 'full' | 'partial' | 'none'
        只在数据变化时刷新
        """
        data_str = json.dumps(state, sort_keys=True, default=str)
        new_hash = hashlib.md5(data_str.encode()).hexdigest()

        if new_hash == self.last_data_hash:
            return "none"

        image = self._draw(state)
        self.last_data_hash = new_hash
        now = time.time()

        if not self.epd:
            # 无硬件模式: 保存为 PNG 用于调试
            image.save("/tmp/eink_preview.png")
            return "none"

        force_full = (now - self.last_full_refresh) > EINK_FORCE_FULL_REFRESH

        if force_full or not self.last_data_hash:
            self.epd.display(self.epd.getbuffer(image))
            self.last_full_refresh = now
            return "full"
        else:
            self.epd.displayPartial(self.epd.getbuffer(image))
            return "partial"

    def _draw(self, state: dict) -> Image.Image:
        """绘制完整仪表盘位图"""
        img = Image.new("1", (self.width, self.height), 1)  # 1=white
        draw = ImageDraw.Draw(img)

        # === 标题栏 ===
        self._draw_title_bar(draw, state)

        # === 卡片行 1: 余额 + 本期消费 ===
        y = 50
        self._draw_card(draw, 10, y, 310, 80, "充值余额",
                        f"¥ {state['balance'].get('total', '--')}",
                        self._balance_subtitle(state))
        self._draw_card(draw, 330, y, 310, 80, "本期消费",
                        f"¥ {state['usage'].get('period_spending', '--')}",
                        self._spending_subtitle(state))

        # === 卡片行 2: 累计消费 + 请求次数 ===
        y = 145
        self._draw_card(draw, 10, y, 310, 80, "累计消费",
                        f"¥ {state['usage'].get('total_spending', '--')}",
                        "")
        self._draw_card(draw, 330, y, 310, 80, "API 请求次数",
                        f"{state['usage'].get('total_requests', 0):,}",
                        f"Tokens: {self._fmt_tokens(state['usage'].get('total_tokens', 0))}")

        # === 上下文窗口 ===
        y = 240
        self._draw_context_bar(draw, 10, y, self.width - 20, state)

        # === 分隔线 ===
        y = 280
        draw.line([(10, y), (self.width - 10, y)], fill=0)

        # === 模型用量 ===
        y = 290
        self._draw_model_usage(draw, 10, y, self.width - 20, state)

        # === 底栏 ===
        y = 420
        self._draw_footer(draw, 10, y, self.width - 20, state)

        return img

    # ─── 子渲染函数 ────────────────────────────────

    def _draw_title_bar(self, draw: ImageDraw.Draw, state: dict) -> None:
        """标题栏: 标题 + 状态指示 + 时间"""
        draw.rectangle([(0, 0), (self.width, 35)], fill=0)  # 黑底
        draw.text((10, 8), "DEEPSEEK", fill=1, font=self.font_title)

        status_text = {
            "idle": "[ ] 空闲", "running": "[*] 运行中",
            "waiting": "[?] 等待", "error": "[X] 故障"
        }.get(state.get("cc_status", "idle"), "[ ] --")

        draw.text((200, 8), status_text, fill=1, font=self.font_small)

        time_str = time.strftime("%H:%M", time.localtime())
        draw.text((self.width - 80, 8), time_str, fill=1, font=self.font_small)

    def _draw_card(self, draw: ImageDraw.Draw, x: int, y: int,
                   w: int, h: int, title: str, value: str, subtitle: str) -> None:
        """通用卡片: 边框 + 标题 + 大号数值 + 副标题"""
        draw.rectangle([(x, y), (x + w, y + h)], outline=0)
        draw.text((x + 8, y + 4), title, fill=0, font=self.font_small)
        draw.text((x + 8, y + 22), value, fill=0, font=self.font_large)
        if subtitle:
            draw.text((x + 8, y + 62), subtitle, fill=0, font=self.font_small)

    def _draw_context_bar(self, draw: ImageDraw.Draw, x: int, y: int,
                          w: int, state: dict) -> None:
        """上下文窗口进度条"""
        pct = state.get("cc_context_percent", 0)
        bar_w = w - 20
        filled = int(bar_w * pct / 100)

        # 背景
        draw.rectangle([(x, y), (x + w, y + 40)], outline=0)
        draw.text((x + 8, y + 2), f"上下文窗口  {pct}%", fill=0, font=self.font_small)

        # 进度条
        bar_y = y + 20
        draw.rectangle([(x + 8, bar_y), (x + 8 + bar_w, bar_y + 12)], outline=0)
        if filled > 0:
            draw.rectangle([(x + 9, bar_y + 1), (x + 8 + filled, bar_y + 11)], fill=0)

        # Compact 阈值线
        threshold_x = x + 8 + int(bar_w * (COMPACT_THRESHOLD_TOKENS / 1000000 * 100) / 100)
        draw.line([(threshold_x, bar_y - 2), (threshold_x, bar_y + 14)], fill=0)
        draw.text((x + 8, bar_y + 14), f"Compact: {COMPACT_THRESHOLD_TOKENS // 1000}K",
                  fill=0, font=self.font_small)

        # 会话信息
        session_start = state.get("cc_session_start")
        if session_start:
            elapsed = int(time.time() - session_start)
            mins = elapsed // 60
            info = f"会话: {mins}min  第{state.get('cc_round', 0)}轮"
            draw.text((x + w - 200, y + 2), info, fill=0, font=self.font_small)

    def _draw_model_usage(self, draw: ImageDraw.Draw, x: int, y: int,
                          w: int, state: dict) -> None:
        """模型用量条形图"""
        draw.text((x, y), "模型用量", fill=0, font=self.font_small)
        models = state.get("usage", {}).get("models", [])
        if not models:
            draw.text((x, y + 20), "(暂无数据)", fill=0, font=self.font_small)
            return

        max_tokens = max(m["tokens"] for m in models) if models else 1
        bar_w = w - 260  # 留空间给文字

        for i, model in enumerate(models):
            by = y + 20 + i * 30
            bar_fill = int(bar_w * model["tokens"] / max_tokens)

            draw.text((x + 8, by), model["name"], fill=0, font=self.font_small)
            draw.rectangle([(x + 180, by + 2), (x + 180 + bar_w, by + 18)], outline=0)
            if bar_fill > 0:
                draw.rectangle([(x + 181, by + 3), (x + 180 + bar_fill, by + 17)], fill=0)

            info = f"{model['requests']:,}次  {self._fmt_tokens(model['tokens'])}"
            draw.text((x + 180 + bar_w + 8, by + 2), info, fill=0, font=self.font_small)

    def _draw_footer(self, draw: ImageDraw.Draw, x: int, y: int,
                     w: int, state: dict) -> None:
        """底栏: 更新时间 + 网络延迟 + 服务健康"""
        last_bal = state.get("last_updated", {}).get("balance", 0)
        if last_bal:
            ago = int(time.time() - last_bal)
            update_text = f"更新: {ago}s前" if ago < 120 else f"更新: {ago // 60}min前"
        else:
            update_text = "更新: --"

        draw.text((x, y), update_text, fill=0, font=self.font_small)

        latency = state.get("network_latency_ms", 0)
        draw.text((x + 160, y), f"延迟: {latency}ms", fill=0, font=self.font_small)

        # 服务健康
        svc = state.get("services", {})
        svc_text = " | ".join(
            f"{k}: {'OK' if v == 'up' else '--'}" for k, v in svc.items()
        )
        draw.text((x, y + 18), svc_text, fill=0, font=self.font_small)

    # ─── 格式化辅助 ────────────────────────────────

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.0f}M"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)

    def _balance_subtitle(self, state: dict) -> str:
        bal = state.get("balance", {})
        if bal.get("is_available"):
            total = float(bal.get("total", 0))
            if total < BALANCE_CRITICAL_THRESHOLD:
                return "[!] 余额严重不足"
            if total < BALANCE_WARN_THRESHOLD:
                return "[!] 余额偏低"
            return "预警已开启"
        return "[!] 余额不足,API 不可用"

    def _spending_subtitle(self, state: dict) -> str:
        """显示消费变动 (需要历史数据)"""
        return ""  # 变动计算留到后续迭代

    def sleep(self) -> None:
        """墨水屏进入休眠 (省电)"""
        if self.epd:
            self.epd.sleep()

    def clear(self) -> None:
        """清屏"""
        if self.epd:
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()
```

- [ ] **Step 2: Commit**

```bash
git add usage-monitor/eink_dashboard.py
git commit -m "feat: add e-ink dashboard renderer with PIL"
```

---

### Task 4: Windows 状态上报器

**Files:**
- Create: `windows-reporter/reporter.py`

**Produces:** 独立脚本，被 CC hooks 调用，HTTP POST 状态到树莓派

- [ ] **Step 1: 写入 reporter.py**

```python
# windows-reporter/reporter.py
"""
Claude Code Hooks 状态上报脚本
用法: python reporter.py <status> [--session-start] [--session-end]

状态值: idle | running | waiting | error | compact-warning
"""

import requests
import sys
import os
import json
import time
import socket

# 树莓派地址 (环境变量覆盖默认值)
PI_URL = os.getenv("PI_MONITOR_URL", "http://raspberrypi.local:5000")


def get_hostname() -> str:
    return os.getenv("COMPUTERNAME", socket.gethostname())


def report(payload: dict) -> None:
    try:
        resp = requests.post(
            f"{PI_URL}/api/status",
            json=payload,
            timeout=5
        )
        if resp.status_code != 200:
            print(f"[reporter] Warning: Pi returned {resp.status_code}", file=sys.stderr)
    except requests.exceptions.ConnectionError:
        print(f"[reporter] Cannot reach Pi at {PI_URL}", file=sys.stderr)
    except requests.exceptions.Timeout:
        print(f"[reporter] Pi timeout", file=sys.stderr)
    except Exception as e:
        print(f"[reporter] Error: {e}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print("Usage: python reporter.py <status> [flags]", file=sys.stderr)
        sys.exit(1)

    status = sys.argv[1]

    payload = {
        "status": status,
        "timestamp": time.time(),
        "host": get_hostname(),
    }

    if "--session-start" in sys.argv:
        payload["session_start"] = True
    if "--session-end" in sys.argv:
        payload["session_end"] = True

    report(payload)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 本地测试 (无 Pi 也可运行)**

```bash
cd D:/pythonProject
# 启动一个简单的 echo server 测试 reporter 能否正常发起请求
python -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(length))
        print(f'Received: {body}')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{\"ok\": true}')
HTTPServer(('localhost', 5000), H).handle_request()
" &
sleep 1
PI_MONITOR_URL=http://localhost:5000 python windows-reporter/reporter.py running
```

预期输出: `Received: {'status': 'running', 'timestamp': ..., 'host': '...'}`

- [ ] **Step 3: Commit**

```bash
git add windows-reporter/reporter.py
git commit -m "feat: add CC hooks status reporter for Windows"
```

---

### Task 5: Claude Code Hooks 配置

**Files:**
- Modify: `~/.claude/settings.local.json` (或项目 `.claude/settings.local.json`)

**Produces:** CC 启动后自动上报状态到树莓派

- [ ] **Step 1: 读取现有 settings.local.json**

检查 `C:\Users\19041\.claude\settings.json` 是否已有 hooks 配置

- [ ] **Step 2: 合并 hooks 配置**

在 settings.json 中新增 `"hooks"` 字段 (与现有配置合并):

```jsonc
{
  // ... 现有配置保持不变 ...
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "idle", "--session-start"],
          "timeout": 10
        }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "running"],
          "timeout": 5,
          "async": true
        }]
      }
    ],
    "PostToolBatch": [
      {
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "running"],
          "timeout": 5,
          "async": true
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "idle"],
          "timeout": 5,
          "async": true
        }]
      }
    ],
    "StopFailure": [
      {
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "error"],
          "timeout": 5,
          "async": true
        }]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt|elicitation_dialog",
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "waiting"],
          "timeout": 5,
          "async": true
        }]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [{
          "type": "command",
          "command": "python",
          "args": ["D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py", "idle", "--session-end"],
          "timeout": 10
        }]
      }
    ]
  }
}
```

- [ ] **Step 3: 验证 hooks 语法**

确保 settings.json 仍是合法 JSON (`python -m json.tool` 检查)

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "feat: add CC hooks config for status reporting"
```

---

### Task 6: Flask 主程序 + 余额获取

**Files:**
- Create: `usage-monitor/app.py`

**Produces:** Flask 服务运行在 :5000，定时拉取 DeepSeek 余额，提供 `/api/dashboard` 和 `/api/status`

- [ ] **Step 1: 写入 app.py**

```python
# usage-monitor/app.py
"""DeepSeek 用量监控 — Flask 主入口"""

import time
import requests
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BALANCE_URL,
    BALANCE_INTERVAL, USAGE_SCRAPE_INTERVAL, EINK_CHECK_INTERVAL,
    FLASK_HOST, FLASK_PORT,
)
from led_controller import LEDController
from eink_dashboard import EinkDashboard

app = Flask(__name__)

# ─── 全局状态 ────────────────────────────────

state = {
    "balance": {},
    "usage": {"period_spending": "0", "total_spending": "0",
               "total_requests": 0, "total_tokens": 0, "models": []},
    "cc_status": "idle",
    "cc_session_start": None,
    "cc_context_percent": 0,
    "cc_round": 0,
    "last_updated": {"balance": 0, "usage": 0},
    "alerts": [],
    "network_latency_ms": 0,
    "services": {"deepseek_api": "unknown"},
}

# ─── 硬件控制器 (延迟初始化) ──────────────────

led: LEDController | None = None
eink: EinkDashboard | None = None

try:
    led = LEDController()
    led.set_status("idle")
    print("[init] LED controller ready")
except Exception as e:
    print(f"[init] LED not available: {e}")

try:
    eink = EinkDashboard()
    eink.init_hardware()
    print("[init] E-ink display ready")
except Exception as e:
    print(f"[init] E-ink not available (mock mode): {e}")
    eink = EinkDashboard()  # 无硬件模式


# ─── 数据采集 ────────────────────────────────

def fetch_balance() -> None:
    """获取 DeepSeek 余额"""
    if not DEEPSEEK_API_KEY:
        print("[balance] DEEPSEEK_API_KEY not set")
        state["services"]["deepseek_api"] = "no_key"
        return

    t0 = time.time()
    try:
        resp = requests.get(
            DEEPSEEK_BALANCE_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            timeout=10,
        )
        state["network_latency_ms"] = int((time.time() - t0) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            infos = data.get("balance_infos", [])
            if infos:
                b = infos[0]
                state["balance"] = {
                    "total": b.get("total_balance", "0"),
                    "currency": b.get("currency", "CNY"),
                    "granted": b.get("granted_balance", "0"),
                    "topped_up": b.get("topped_up_balance", "0"),
                    "is_available": data.get("is_available", False),
                }
                state["services"]["deepseek_api"] = "up"

                # 余额预警
                total = float(state["balance"]["total"])
                from config import BALANCE_WARN_THRESHOLD, BALANCE_CRITICAL_THRESHOLD
                if total < BALANCE_CRITICAL_THRESHOLD:
                    state["alerts"] = [{"level": "critical",
                                        "message": f"余额仅剩 ¥{total:.2f}"}]
                elif total < BALANCE_WARN_THRESHOLD:
                    state["alerts"] = [{"level": "warning",
                                        "message": f"余额低于 ¥{BALANCE_WARN_THRESHOLD}"}]
                else:
                    state["alerts"] = []

            state["last_updated"]["balance"] = time.time()
        else:
            state["services"]["deepseek_api"] = f"error_{resp.status_code}"
            print(f"[balance] API error: {resp.status_code}")

    except requests.exceptions.Timeout:
        state["network_latency_ms"] = 999
        state["services"]["deepseek_api"] = "timeout"
    except Exception as e:
        print(f"[balance] fetch error: {e}")
        state["services"]["deepseek_api"] = "error"


# ─── API 路由 ────────────────────────────────

@app.route("/api/dashboard")
def dashboard():
    return jsonify(state)


@app.route("/api/status", methods=["POST"])
def update_status():
    data = request.get_json() or {}
    new_status = data.get("status", "idle")

    if new_status != state["cc_status"]:
        state["cc_status"] = new_status
        if led:
            led.set_status(new_status)

        # compact-warning 不计入 LED 状态变化，只更新上下文进度
        if new_status == "compact-warning":
            state["cc_context_percent"] = min(state["cc_context_percent"] + 10, 95)
        elif new_status == "error":
            state["cc_context_percent"] = 0  # 错误时重置

    if data.get("session_start"):
        state["cc_session_start"] = time.time()
        state["cc_round"] = 0
        state["cc_context_percent"] = 0

    if data.get("session_end"):
        state["cc_session_start"] = None
        state["cc_round"] = 0
        state["cc_context_percent"] = 0

    # 每次状态更新触发墨水屏检查
    if eink:
        eink.render(state)

    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "cc_status": state["cc_status"]})


# ─── 启动 ────────────────────────────────────

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_balance, "interval", seconds=BALANCE_INTERVAL)
    scheduler.add_job(lambda: eink and eink.render(state),
                      "interval", seconds=EINK_CHECK_INTERVAL)
    scheduler.start()

    # 启动时立即获取一次
    fetch_balance()

    print(f"[app] Starting on {FLASK_HOST}:{FLASK_PORT}")
    try:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
    finally:
        if led:
            led.cleanup()
        if eink:
            eink.sleep()
```

- [ ] **Step 2: 验证无硬件启动**

```bash
cd D:/pythonProject
# 在 Windows 上测试 Flask 能否正常启动 (LED/Eink 会自动降级)
pip install flask apscheduler requests
DEEPSEEK_API_KEY=test python usage-monitor/app.py &
sleep 3
curl http://localhost:5000/api/dashboard | python -m json.tool
curl -X POST http://localhost:5000/api/status \
  -H "Content-Type: application/json" \
  -d '{"status": "running"}'
curl http://localhost:5000/api/dashboard | python -m json.tool
```

预期: `/api/dashboard` 返回完整 state JSON, `cc_status` 变为 `"running"`

- [ ] **Step 3: Commit**

```bash
git add usage-monitor/app.py
git commit -m "feat: add Flask app with balance fetcher and status API"
```

---

### Task 7: Playwright 用量抓取

**Files:**
- Create: `usage-monitor/usage_scraper.py`

**Produces:** `fetch_usage(state)` 函数，登录 DeepSeek Platform 抓取用量数据

- [ ] **Step 1: 写入用法抓取器**

```python
# usage-monitor/usage_scraper.py
"""DeepSeek Platform 用量抓取 — Playwright 自动化"""

import asyncio
import json
import time
from pathlib import Path
from config import DEEPSEEK_PLATFORM_URL, DEEPSEEK_USAGE_URL, AUTH_STATE_FILE


class LoginExpiredError(Exception):
    pass


def fetch_usage_sync(state: dict) -> None:
    """同步包装器，供 APScheduler 调用"""
    try:
        asyncio.run(_fetch_usage(state))
    except LoginExpiredError:
        print("[usage] Login expired, need re-auth")
        state["services"]["deepseek_platform"] = "login_expired"
    except Exception as e:
        print(f"[usage] Scrape error: {e}")
        state["services"]["deepseek_platform"] = "error"


async def _fetch_usage(state: dict) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        storage = str(AUTH_STATE_FILE) if AUTH_STATE_FILE.exists() else None

        context = await browser.new_context(
            storage_state=storage,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            await page.goto(DEEPSEEK_USAGE_URL, wait_until="networkidle", timeout=30000)

            if "login" in page.url.lower():
                await browser.close()
                raise LoginExpiredError("Need login")

            # 等待用量数据加载
            await page.wait_for_timeout(3000)

            # 提取数据 (选择器需根据 DeepSeek 实际页面调整)
            data = await page.evaluate("""() => {
                const result = { period_spending: '0', total_spending: '0',
                                  total_requests: 0, total_tokens: 0, models: [] };

                // 尝试从页面提取用量数据
                // 具体选择器需要在 DeepSeek Platform 实际页面中确认
                const text = document.body.innerText;
                return result;
            }""")

            state["usage"] = data
            state["last_updated"]["usage"] = time.time()
            state["services"]["deepseek_platform"] = "up"

            # 保存登录态
            await context.storage_state(path=str(AUTH_STATE_FILE))

        finally:
            await browser.close()


def login_interactive() -> None:
    """交互式登录: 打开浏览器让用户手动登录, 保存 cookie

    树莓派上运行需要 DISPLAY 环境变量或 headless 模式下的 OAuth
    """
    import subprocess
    import sys

    print("=" * 50)
    print("请在浏览器中登录 DeepSeek Platform")
    print(f"登录后, cookie 将保存到: {AUTH_STATE_FILE}")
    print("=" * 50)

    code = """
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://platform.deepseek.com")
        print("请在浏览器中完成登录...")
        await page.wait_for_url("**/usage**", timeout=300000)
        await page.context.storage_state(path="AUTH_FILE")
        print("登录态已保存!")
        await browser.close()

asyncio.run(main())
""".replace("AUTH_FILE", str(AUTH_STATE_FILE))

    subprocess.run([sys.executable, "-c", code])
```

- [ ] **Step 2: 首次登录**

```bash
# 在树莓派上 (需要接显示器或 VNC)
cd /home/pi/usage-monitor
python -c "from usage_scraper import login_interactive; login_interactive()"
```

- [ ] **Step 3: Commit**

```bash
git add usage-monitor/usage_scraper.py
git commit -m "feat: add Playwright scraper for DeepSeek platform usage"
```

---

### Task 8: 树莓派环境搭建 + 首次部署

**Files:**
- Create: `usage-monitor/monitor.service`

**Produces:** 树莓派上系统就绪，Flask 运行，墨水屏工作

- [ ] **Step 1: 烧录 Raspberry Pi OS**

使用 Raspberry Pi Imager 烧录 Raspberry Pi OS Lite (Bookworm, 64-bit) 到 MicroSD 卡，预配置 WiFi 和 SSH

- [ ] **Step 2: 树莓派初始设置**

```bash
# SSH 登录树莓派
ssh pi@raspberrypi.local

# 启用 SPI (墨水屏需要)
sudo raspi-config nonint do_spi 0

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装依赖
sudo apt install -y python3-pip python3-venv git chromium-browser \
  fonts-dejavu-core

# 创建项目目录
mkdir -p /home/pi/usage-monitor
```

- [ ] **Step 3: 传输代码到树莓派**

```bash
# 在 Windows 上
scp -r D:/pythonProject/deepseek-usage-monitor/usage-monitor/* pi@raspberrypi.local:/home/pi/usage-monitor/
```

- [ ] **Step 4: 树莓派上安装 Python 依赖**

```bash
ssh pi@raspberrypi.local
cd /home/pi/usage-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gpiozero  # 通常已预装

# 安装 Playwright (仅需要 chromium)
pip install playwright
playwright install chromium
```

- [ ] **Step 5: 安装墨水屏驱动**

```bash
# 克隆 Waveshare 官方库
cd /tmp
git clone https://github.com/waveshareteam/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
pip install .
# 或直接复制 epd5in83_V2.py 到项目中
```

- [ ] **Step 6: 写 systemd service 文件**

```ini
# usage-monitor/monitor.service
[Unit]
Description=DeepSeek Usage Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/usage-monitor
Environment="DEEPSEEK_API_KEY=sk-your-key-here"
Environment="PI_MONITOR_URL=http://localhost:5000"
ExecStart=/home/pi/usage-monitor/venv/bin/python /home/pi/usage-monitor/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 7: 启用服务**

```bash
sudo cp /home/pi/usage-monitor/monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable monitor
sudo systemctl start monitor

# 检查状态
sudo systemctl status monitor
curl http://localhost:5000/api/dashboard
```

- [ ] **Step 8: Commit**

```bash
git add usage-monitor/monitor.service
git commit -m "feat: add systemd service for auto-start"
```

---

### Task 9: GPIO LED 接线 + 测试

- [ ] **Step 1: 物理接线**

```
树莓派 GPIO (BCM):
  GPIO 17 (Pin 11) ──→ 220Ω ──→ 红色 LED (+) → LED (-) → GND (Pin 9)
  GPIO 27 (Pin 13) ──→ 220Ω ──→ 绿色 LED (+) → LED (-) → GND (Pin 14)
```

- [ ] **Step 2: 测试 LED**

```bash
ssh pi@raspberrypi.local
cd /home/pi/usage-monitor
source venv/bin/activate
python -c "
from led_controller import LEDController
import time
led = LEDController()
for s in ['idle', 'running', 'waiting', 'error']:
    print(f'Status: {s}')
    led.set_status(s)
    time.sleep(3)
led.cleanup()
"
```

预期: 绿灯 → 黄灯常亮 → 黄灯闪烁 → 红灯 → 熄灭

- [ ] **Step 3: Commit**

```
(无代码变更，接线完成后在 checklist 中打勾)
```

---

### Task 10: 墨水屏接线 + 首次渲染测试

- [ ] **Step 1: 安装墨水屏 HAT**

将 Waveshare 5.83" HAT 直接插在树莓派 GPIO 排针上（或通过排线连接 SPI 引脚）

- [ ] **Step 2: 测试驱动**

```bash
ssh pi@raspberrypi.local
cd /home/pi/usage-monitor
source venv/bin/activate

# 测试墨水屏初始化
python -c "
from eink_dashboard import EinkDashboard
eink = EinkDashboard()
eink.init_hardware()

# 渲染测试数据
test_state = {
    'balance': {'total': '16.58', 'currency': 'CNY', 'is_available': True},
    'usage': {'period_spending': '79.41', 'total_spending': '203.41',
              'total_requests': 6738, 'total_tokens': 518230239,
              'models': [
                  {'name': 'deepseek-v4-flash', 'requests': 2840, 'tokens': 221051931},
                  {'name': 'deepseek-v4-pro', 'requests': 3898, 'tokens': 297178308}
              ]},
    'cc_status': 'idle',
    'cc_session_start': None,
    'cc_context_percent': 82,
    'cc_round': 3,
    'last_updated': {},
    'alerts': [],
    'network_latency_ms': 32,
    'services': {'deepseek_api': 'up'},
}
result = eink.render(test_state)
print(f'Render result: {result}')
eink.sleep()
"
```

预期: 墨水屏显示完整仪表盘，`result` 为 `"full"`

- [ ] **Step 3: 测试分层刷新**

```bash
python -c "
from eink_dashboard import EinkDashboard
eink = EinkDashboard()
eink.init_hardware()

# 第一次: 全刷
s1 = {'cc_status': 'idle', 'balance': {'total': '16.58'}, ...}
r1 = eink.render(s1)
print(f'First render: {r1}')  # full

# 同数据: 不刷
r2 = eink.render(s1)
print(f'Same data: {r2}')      # none

# 状态变化: 局刷
s2 = {**s1, 'cc_status': 'running'}
r3 = eink.render(s2)
print(f'Status change: {r3}')  # partial
eink.sleep()
"
```

- [ ] **Step 4: Commit**

```
(无代码变更)
```

---

### Task 11: 树莓派外壳组装

- [ ] **Step 1: 组装**

将所有组件装入外壳:
- 树莓派固定
- 墨水屏嵌入前面板
- LED 固定在屏幕边缘（用热熔胶或螺丝）
- 电源线从背面引出

- [ ] **Step 2: 最终外观检查**

确保 LED 可见、屏幕无遮挡、散热孔通畅

---

### Task 12: 端到端联调

- [ ] **Step 1: 确认 Pi IP 地址**

```bash
ssh pi@raspberrypi.local
hostname -I
# 记下 IP, 例如 192.168.1.100
```

- [ ] **Step 2: 设置 Windows 环境变量**

```bash
# 在 Windows 上 (CMD 或 PowerShell)
setx PI_MONITOR_URL "http://192.168.1.100:5000"
```

或直接在 reporter.py 中硬编码默认 IP

- [ ] **Step 3: Windows reporter 联调**

```bash
cd D:/pythonProject
PI_MONITOR_URL=http://192.168.1.100:5000 python windows-reporter/reporter.py running
# 在 Pi 上确认:
curl http://localhost:5000/api/dashboard | python -m json.tool | grep cc_status
# 预期: "cc_status": "running"
```

- [ ] **Step 4: CC hooks 联调**

重新启动 Claude Code，检查:
1. 启动后 LED 是否变绿
2. 发送一条消息后 LED 是否变黄
3. 响应完成后 LED 是否变回绿
4. 墨水屏是否在数据变化时自动刷新

- [ ] **Step 5: 余额预警测试**

临时降低阈值测试:
```bash
# 修改 config.py 中的 BALANCE_WARN_THRESHOLD 为高值
# 重启 Pi 服务
sudo systemctl restart monitor
# 确认仪表盘显示余额预警
```

- [ ] **Step 6: 长期运行测试**

运行 24 小时，检查:
- 墨水屏残影积累情况 → 确认 30min 强制全刷生效
- LED 无异常闪烁
- Flask 内存无泄漏
- systemd 无意外重启

---

## 附录: 调试命令速查

```bash
# Pi 服务管理
sudo systemctl status monitor     # 查看服务状态
sudo systemctl restart monitor    # 重启
sudo journalctl -u monitor -f     # 实时日志

# 手动测试 API
curl http://localhost:5000/health
curl http://localhost:5000/api/dashboard | python -m json.tool
curl -X POST http://localhost:5000/api/status \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}'

# Windows reporter 手动测试
PI_MONITOR_URL=http://192.168.1.100:5000 python windows-reporter/reporter.py idle

# 查看墨水屏预览 (在 Pi 上)
feh /tmp/eink_preview.png  # 如果有桌面环境
```

## 附录: 采购清单

| 序号 | 物品 | 规格 | 数量 | 约价 | 链接关键词 |
|------|------|------|------|------|-----------|
| 1 | 树莓派 | 3B+ / 4B (1GB+) | 1 | ¥200-350 | "树莓派4B" |
| 2 | MicroSD | 32GB+ Class 10 | 1 | ¥30 | "树莓派内存卡" |
| 3 | 电源 | 5V 3A Type-C | 1 | ¥25 | "树莓派电源 5V 3A" |
| 4 | 墨水屏 | Waveshare 5.83" e-Paper HAT V2 | 1 | ¥150-180 | "微雪 5.83寸 墨水屏" |
| 5 | LED 红 | 3mm/5mm | 1 | ¥0.5 | "LED 红色 5mm" |
| 6 | LED 绿 | 3mm/5mm | 1 | ¥0.5 | "LED 绿色 5mm" |
| 7 | 电阻 | 220Ω 1/4W | 2 | ¥0.5 | "220欧姆电阻" |
| 8 | 杜邦线 | 公对母 10cm | 6根 | ¥3 | "杜邦线 公对母" |
| 9 | 面包板 | 170孔迷你 | 1 | ¥5 | "迷你面包板" |
| 10 | 散热片 | 树莓派套装 | 1套 | ¥5 | "树莓派散热片" |
| 11 | 外壳 | 定制/通用 | 1 | ¥30-60 | "树莓派 墨水屏 外壳" |

**已有树莓派总计: ~¥200 | 全套总计: ~¥450-680**
