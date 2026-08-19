"""DeepSeek 用量监控 — 全局配置"""

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

# ─── DeepSeek API ────────────────────────────

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
DEEPSEEK_PLATFORM_URL = "https://platform.deepseek.com"
DEEPSEEK_USAGE_URL = "https://platform.deepseek.com/usage"

# ─── Flask 服务 ──────────────────────────────

FLASK_HOST = "0.0.0.0"
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

# LAN API 鉴权: 设置后 /api/status 与 /api/dashboard 需要 Header
#   X-Monitor-Token: <token>
# 空字符串 = 关闭鉴权 (仅建议内网调试)
MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "")

# ─── 刷新间隔 (秒) ─────────────────────────────

BALANCE_INTERVAL = 60            # DeepSeek 余额 API
USAGE_SCRAPE_INTERVAL = 300      # cookie REST 用量抓取
EINK_CHECK_INTERVAL = 30         # 墨水屏渲染检查
EINK_FORCE_FULL_REFRESH = 1800   # 每 30 分钟强制全刷清残影
WEATHER_INTERVAL = 1200          # 天气 20 分钟

# Playwright 回退默认关闭 (Pi 上易 OOM); 设 ENABLE_PLAYWRIGHT_FALLBACK=1 启用
ENABLE_PLAYWRIGHT_FALLBACK = os.getenv(
    "ENABLE_PLAYWRIGHT_FALLBACK", "0"
).strip().lower() in ("1", "true", "yes", "on")

# Platform 登录过期后降频重试 (秒)
USAGE_LOGIN_BACKOFF = int(os.getenv("USAGE_LOGIN_BACKOFF", "3600"))

# ─── 天气 ─────────────────────────────────────

WEATHER_CITY = os.getenv("WEATHER_CITY", "Nanjing")

# ─── 余额预警阈值 (CNY) ────────────────────────

BALANCE_WARN_THRESHOLD = 10.0
BALANCE_CRITICAL_THRESHOLD = 5.0

# ─── 上下文窗口 / Claude Code 会话展示 ─────────

COMPACT_THRESHOLD_TOKENS = 850000  # 对齐 CLAUDE_CODE_AUTO_COMPACT_WINDOW

# False: 墨水屏不绘制上下文%/会话$/上一会话（CC hooks/reporter 已停用；API 仍可收上报）
# 恢复显示: 改为 True 即可（需自行恢复 hooks 才有实时数据）
SHOW_CC_CONTEXT = False

# ─── Orchestra 状态面板 (subsystem-4) ─────────

SHOW_ORCHESTRA = True        # 面板开关 (Task 2 起由 eink_dashboard 消费)
ORCHESTRA_STALE_SEC = 90     # 新鲜度阈值 = 3 × Broker poll 30s

# ─── GPIO 引脚 (BCM 编号) ─────────────────────

LED_RED_PIN = int(os.getenv("LED_RED_PIN", "5"))
LED_GREEN_PIN = int(os.getenv("LED_GREEN_PIN", "6"))

# ─── 墨水屏 ───────────────────────────────────

EINK_WIDTH = 800
EINK_HEIGHT = 480

# ─── 认证文件 ─────────────────────────────────

AUTH_STATE_FILE = Path(
    os.getenv("AUTH_STATE_FILE", str(_ROOT / "auth_state.json"))
)
