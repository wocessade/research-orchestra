"""DeepSeek 用量监控 — Flask 主入口

启动方式:
  DEEPSEEK_API_KEY=sk-xxx python app.py

API:
  GET  /api/dashboard   - 完整状态
  POST /api/status      - CC 状态上报
  GET  /health          - 健康检查
"""

import time
import requests
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BALANCE_URL,
    BALANCE_INTERVAL, USAGE_SCRAPE_INTERVAL, EINK_CHECK_INTERVAL,
    BALANCE_WARN_THRESHOLD, BALANCE_CRITICAL_THRESHOLD,
    FLASK_HOST, FLASK_PORT,
)

app = Flask(__name__)

# ─── 全局状态 ──────────────────────────────────

state = {
    "balance": {},
    "usage": {
        "period_spending": "0",
        "total_spending": "0",
        "total_requests": 0,
        "total_tokens": 0,
        "models": [],
    },
    "cc_status": "idle",
    "cc_session_start": None,
    "cc_context_percent": 0,
    "cc_round": 0,
    "last_updated": {"balance": 0, "usage": 0},
    "alerts": [],
    "network_latency_ms": 0,
    "services": {
        "deepseek_api": "unknown",
        "deepseek_platform": "unknown",
    },
}

# ─── 硬件控制器 (延迟初始化, 无硬件时降级) ─────

led = None
eink = None

try:
    from led_controller import LEDController
    led = LEDController()
    led.set_status("idle")
    print("[init] LED controller ready")
except Exception as e:
    print(f"[init] LED not available (expected on non-Pi): {e}")

try:
    from eink_dashboard import EinkDashboard
    eink = EinkDashboard()
    eink.init_hardware()
    print("[init] E-ink display ready")
except Exception as e:
    print(f"[init] E-ink not available (mock mode, saves PNG): {e}")
    eink = EinkDashboard()


# ─── 数据采集 ──────────────────────────────────

def fetch_balance() -> None:
    """获取 DeepSeek 账户余额 (每 60s)"""
    if not DEEPSEEK_API_KEY:
        print("[balance] DEEPSEEK_API_KEY not set — skipping")
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
                _check_balance_alerts()
            state["last_updated"]["balance"] = time.time()
        else:
            state["services"]["deepseek_api"] = f"http_{resp.status_code}"
            print(f"[balance] API returned {resp.status_code}")

    except requests.exceptions.Timeout:
        state["network_latency_ms"] = 999
        state["services"]["deepseek_api"] = "timeout"
    except requests.exceptions.ConnectionError:
        state["services"]["deepseek_api"] = "connection_error"
    except Exception as e:
        print(f"[balance] Unexpected error: {e}")
        state["services"]["deepseek_api"] = "error"


def _check_balance_alerts() -> None:
    """检查余额并生成预警"""
    total_str = state["balance"].get("total", "0")
    try:
        total = float(total_str)
    except (ValueError, TypeError):
        return

    if total < BALANCE_CRITICAL_THRESHOLD:
        state["alerts"] = [{
            "level": "critical",
            "message": f"余额仅剩 {total_str}",
        }]
    elif total < BALANCE_WARN_THRESHOLD:
        state["alerts"] = [{
            "level": "warning",
            "message": f"余额低于 {BALANCE_WARN_THRESHOLD}",
        }]
    else:
        state["alerts"] = []


def _refresh_eink() -> None:
    """APScheduler 回调: 检查并刷新墨水屏"""
    if eink:
        result = eink.render(state)
        if result != "none":
            print(f"[eink] Refreshed: {result}")


# ─── API 路由 ──────────────────────────────────

@app.route("/api/dashboard")
def dashboard():
    """返回完整监控状态"""
    return jsonify(state)


@app.route("/api/status", methods=["POST"])
def update_status():
    """接收 Windows CC hooks 上报的状态

    Body: {
      "status": "idle|running|waiting|error|compact-warning",
      "timestamp": 1721548800.0,
      "host": "DESKTOP-XXX",
      "session_start": true,    // optional
      "session_end": true       // optional
    }
    """
    data = request.get_json() or {}
    new_status = data.get("status", "idle")

    # 更新 CC 状态 → LED + E-ink
    if new_status != state["cc_status"]:
        state["cc_status"] = new_status
        if led:
            led.set_status(new_status)

        # compact-warning: 提高上下文百分比, 但不改 LED
        if new_status == "compact-warning":
            state["cc_context_percent"] = min(
                state["cc_context_percent"] + 10, 95
            )
        elif new_status == "error":
            pass  # 保持当前上下文数据

    # 会话生命周期
    if data.get("session_start"):
        state["cc_session_start"] = time.time()
        state["cc_round"] = 0
        state["cc_context_percent"] = 0

    if data.get("session_end"):
        state["cc_session_start"] = None
        state["cc_round"] = 0
        state["cc_context_percent"] = 0

    # 触达墨水屏更新
    if eink:
        eink.render(state)

    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "cc_status": state["cc_status"],
        "services": state["services"],
    })


# ─── 启动 ──────────────────────────────────────

if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    # 定时任务
    scheduler.add_job(fetch_balance, "interval", seconds=BALANCE_INTERVAL)
    scheduler.add_job(_refresh_eink, "interval", seconds=EINK_CHECK_INTERVAL)

    # 用量抓取 (需要 Playwright, 可能较重)
    try:
        from usage_scraper import fetch_usage_sync
        scheduler.add_job(
            lambda: fetch_usage_sync(state),
            "interval",
            seconds=USAGE_SCRAPE_INTERVAL,
        )
        print("[init] Usage scraper scheduled")
    except ImportError as e:
        print(f"[init] Usage scraper not available: {e}")

    scheduler.start()

    # 启动时立即拉取一次余额
    fetch_balance()

    print(f"[app] Listening on {FLASK_HOST}:{FLASK_PORT}")
    try:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
    finally:
        if led:
            led.cleanup()
            print("[app] LED cleaned up")
        if eink:
            eink.sleep()
            print("[app] E-ink sleeping")
