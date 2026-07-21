"""DeepSeek 用量监控 — 全局配置"""

import os

# ─── DeepSeek API ────────────────────────────

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
DEEPSEEK_PLATFORM_URL = "https://platform.deepseek.com"
DEEPSEEK_USAGE_URL = "https://platform.deepseek.com/usage"

# ─── Flask 服务 ──────────────────────────────

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# ─── 刷新间隔 (秒) ─────────────────────────────

BALANCE_INTERVAL = 60            # DeepSeek 余额 API
USAGE_SCRAPE_INTERVAL = 300      # Playwright 用量抓取
EINK_CHECK_INTERVAL = 30         # 墨水屏渲染检查
EINK_FORCE_FULL_REFRESH = 1800   # 每 30 分钟强制全刷清残影

# ─── 余额预警阈值 (CNY) ────────────────────────

BALANCE_WARN_THRESHOLD = 10.0
BALANCE_CRITICAL_THRESHOLD = 5.0

# ─── 上下文窗口 ───────────────────────────────

COMPACT_THRESHOLD_TOKENS = 850000  # 对齐 CLAUDE_CODE_AUTO_COMPACT_WINDOW

# ─── GPIO 引脚 (BCM 编号) ─────────────────────

LED_RED_PIN = 17
LED_GREEN_PIN = 27

# ─── 墨水屏 ───────────────────────────────────

EINK_WIDTH = 648
EINK_HEIGHT = 480

# ─── 认证文件 ─────────────────────────────────

AUTH_STATE_FILE = os.path.join(os.path.dirname(__file__), "auth_state.json")
