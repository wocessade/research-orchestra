"""DeepSeek 用量监控 — Flask 主入口

启动方式:
  DEEPSEEK_API_KEY=sk-xxx python app.py

API:
  GET  /api/dashboard   - 完整状态
  POST /api/status      - CC 状态上报
  POST /api/orchestra   - Orchestra 状态上报
  GET  /health          - 健康检查
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from functools import wraps

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request

_ROOT = os.path.dirname(os.path.abspath(__file__))
# Runtime driver locations (Pi deploy + vendor tree in this repo)
for _p in (
    os.path.join(_ROOT, "waveshare_epd"),
    os.path.join(
        _ROOT,
        "waveshare_driver",
        "RaspberryPi_JetsonNano",
        "python",
        "lib",
    ),
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from config import (  # noqa: E402
    DEEPSEEK_API_KEY,
    DEEPSEEK_BALANCE_URL,
    BALANCE_INTERVAL,
    USAGE_SCRAPE_INTERVAL,
    EINK_CHECK_INTERVAL,
    WEATHER_INTERVAL,
    SELF_STATUS_INTERVAL,
    USAGE_LOGIN_BACKOFF,
    BALANCE_WARN_THRESHOLD,
    BALANCE_CRITICAL_THRESHOLD,
    FLASK_HOST,
    FLASK_PORT,
    MONITOR_TOKEN,
    LED_RED_PIN,
    LED_GREEN_PIN,
    SHOW_ORCHESTRA,
    ORCHESTRA_STALE_SEC,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("monitor")

app = Flask(__name__)

# ─── 全局状态 ──────────────────────────────────

state_lock = threading.RLock()

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
    "cc_panel": "idle",  # idle | active
    "cc_session_start": None,
    "cc_context_percent": 0,
    "cc_context_peak": 0,
    "cc_round": 0,
    "cc_session_cost_usd": 0.0,
    "cc_model": "",
    "cc_session_id": "",
    "last_session": {},  # session_end 后冻结的摘要
    "weather": {},
    "orchestra": {
        "broker_health": "unknown",
        "queue_len": None,
        "active_tasks": None,
        "last_task": None,
        "last_sync": None,
        "recent_tasks": [],
        "host": {},  # Broker 所在设备负载/内存 (broker 上报)
    },
    "orchestra_last_report": {"broker": 0, "sync": 0},  # epoch 秒, 无上报 = 0
    "self_status": {"load1": None, "mem_pct": None},  # 本机 (核桃派) 负载/内存
    "last_updated": {"balance": 0, "usage": 0, "status": 0, "weather": 0},
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
_eink_lock = threading.Lock()
_eink_wake = threading.Event()
_eink_stop = threading.Event()
_eink_thread: threading.Thread | None = None
_eink_fail_count = 0
_usage_login_backoff_until = 0.0

try:
    from led_controller import LEDController

    led = LEDController(red_pin=LED_RED_PIN, green_pin=LED_GREEN_PIN)
    led.set_status("idle")
    log.info("LED controller ready (R=%s G=%s)", LED_RED_PIN, LED_GREEN_PIN)
except Exception as e:
    log.warning("LED not available (expected on non-Pi): %s", e)

try:
    from eink_dashboard import EinkDashboard

    eink = EinkDashboard()
    eink.init_hardware()
    log.info("E-ink display ready")
except Exception as e:
    log.warning("E-ink not available (mock mode): %s", e)
    try:
        from eink_dashboard import EinkDashboard

        eink = EinkDashboard()
    except Exception:
        eink = None


# ─── 鉴权 ─────────────────────────────────────

def _check_token() -> bool:
    if not MONITOR_TOKEN:
        return True
    return request.headers.get("X-Monitor-Token", "") == MONITOR_TOKEN


def require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _check_token():
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


# ─── 数据采集 ──────────────────────────────────

def fetch_balance() -> None:
    """获取 DeepSeek 账户余额 (每 60s)"""
    if not DEEPSEEK_API_KEY:
        log.warning("DEEPSEEK_API_KEY not set — skipping balance")
        with state_lock:
            state["services"]["deepseek_api"] = "no_key"
        return

    t0 = time.time()
    try:
        resp = requests.get(
            DEEPSEEK_BALANCE_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            timeout=10,
        )
        latency = int((time.time() - t0) * 1000)
        with state_lock:
            state["network_latency_ms"] = latency
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
                    _check_balance_alerts_unlocked()
                state["last_updated"]["balance"] = time.time()
                changed = True
            else:
                state["services"]["deepseek_api"] = f"http_{resp.status_code}"
                log.warning("Balance API returned %s", resp.status_code)
                changed = False

        if changed:
            _request_eink_refresh()

    except requests.exceptions.Timeout:
        with state_lock:
            state["network_latency_ms"] = 999
            state["services"]["deepseek_api"] = "timeout"
    except requests.exceptions.ConnectionError:
        with state_lock:
            state["services"]["deepseek_api"] = "connection_error"
    except Exception as e:
        log.exception("Balance unexpected error: %s", e)
        with state_lock:
            state["services"]["deepseek_api"] = "error"


def _check_balance_alerts_unlocked() -> None:
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


def _request_eink_refresh() -> None:
    """请求后台刷屏 (coalesce: 多次请求合并为一次)。HTTP 路径勿同步 SPI。"""
    if not eink:
        return
    _eink_wake.set()


def _eink_worker_loop() -> None:
    """单 worker: 等唤醒 → 短暂 coalesce → 持锁刷屏。异常隔离不打崩进程。"""
    global _eink_fail_count
    while not _eink_stop.is_set():
        woken = _eink_wake.wait(timeout=1.0)
        if _eink_stop.is_set():
            break
        if not woken:
            continue
        # coalesce 突发 hooks
        time.sleep(0.05)
        _eink_wake.clear()
        if not eink:
            continue
        try:
            with _eink_lock:
                result = eink.render(_snapshot_state())
            _eink_fail_count = 0
            if result != "none":
                log.info("E-ink refreshed: %s", result)
        except Exception as e:
            _eink_fail_count += 1
            log.exception("E-ink render failed (%s): %s", _eink_fail_count, e)
            _recover_eink()
            # 连续失败退避, 避免 SPI 忙循环
            if _eink_fail_count >= 3:
                time.sleep(min(30, 5 * _eink_fail_count))


def _recover_eink() -> None:
    """SPI/驱动异常后尝试 re-init。"""
    if not eink:
        return
    try:
        with _eink_lock:
            if getattr(eink, "epd", None):
                try:
                    eink.epd.init()
                except Exception:
                    eink.init_hardware()
            else:
                eink.init_hardware()
        log.info("E-ink re-initialized after failure")
    except Exception as e:
        log.warning("E-ink recovery failed: %s", e)


def _start_eink_worker() -> None:
    global _eink_thread
    if not eink or _eink_thread is not None:
        return
    _eink_stop.clear()
    _eink_thread = threading.Thread(
        target=_eink_worker_loop, name="eink-worker", daemon=True
    )
    _eink_thread.start()
    log.info("E-ink background worker started")


def _stop_eink_worker() -> None:
    _eink_stop.set()
    _eink_wake.set()
    t = _eink_thread
    if t and t.is_alive():
        t.join(timeout=3)


def _refresh_eink() -> None:
    """APScheduler 回调: 请求检查并刷新墨水屏"""
    _request_eink_refresh()


def _run_usage_scrape() -> None:
    """网络 I/O 在锁外; 仅写回 state 时持锁。登录过期降频重试。"""
    global _usage_login_backoff_until
    now = time.time()
    if now < _usage_login_backoff_until:
        log.debug(
            "Usage scrape skipped (login backoff %.0fs left)",
            _usage_login_backoff_until - now,
        )
        return

    from usage_scraper import scrape_usage

    result = scrape_usage()
    with state_lock:
        if result.get("ok"):
            state["usage"] = result["usage"]
            state["last_updated"]["usage"] = time.time()
            state["services"]["deepseek_platform"] = "up"
            _usage_login_backoff_until = 0.0
        else:
            svc = result.get("service", "error")
            state["services"]["deepseek_platform"] = svc
            # 保留旧 usage; 登录过期进入退避
            if svc == "login_expired":
                _usage_login_backoff_until = time.time() + USAGE_LOGIN_BACKOFF
                log.warning(
                    "Platform login expired — backoff %ss, re-run: "
                    "python usage_scraper.py login",
                    USAGE_LOGIN_BACKOFF,
                )
    _request_eink_refresh()


def _run_weather() -> None:
    """网络 I/O 在锁外; 仅写回 state 时持锁。"""
    from weather import fetch_weather

    weather = fetch_weather()
    if not weather:
        return
    with state_lock:
        state["weather"] = weather
        state["last_updated"]["weather"] = time.time()
    _request_eink_refresh()


def read_self_status(
    loadavg_path: str = "/proc/loadavg",
    meminfo_path: str = "/proc/meminfo",
) -> dict:
    """读本机负载/内存 (Linux /proc)。文件缺失/解析失败 → 全 None。

    load1 = /proc/loadavg 第一字段, 四舍五入保留 1 位小数;
    mem_pct = round((MemTotal - MemAvailable) / MemTotal * 100) 整数。
    """
    status = {"load1": None, "mem_pct": None}
    try:
        with open(loadavg_path, "r", encoding="utf-8") as f:
            parts = f.read().split()
        status["load1"] = round(float(parts[0]), 1)
    except (OSError, ValueError, IndexError):
        pass
    try:
        fields = {}
        with open(meminfo_path, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    key, _, rest = line.partition(":")
                    fields[key] = rest.split()[0]
        total = int(fields["MemTotal"])
        avail = int(fields["MemAvailable"])
        if total > 0:
            status["mem_pct"] = round((total - avail) / total * 100)
    except (OSError, ValueError, KeyError, IndexError):
        pass
    return status


def _run_self_status() -> None:
    """本机负载/内存: 锁外读, 变化时锁内写 + 请求局刷 (与 weather 同模式)"""
    status = read_self_status()
    with state_lock:
        if state.get("self_status") == status:
            return
        state["self_status"] = status
    _request_eink_refresh()


def _resolve_panel(status: str, current: str) -> str:
    if status in ("running", "waiting"):
        return "active"
    if status == "idle":
        return "idle"
    return current  # error / compact-warning: 保持


def _snapshot_state() -> dict:
    with state_lock:
        snap = dict(state)
        snap["balance"] = dict(state.get("balance") or {})
        snap["usage"] = dict(state.get("usage") or {})
        snap["services"] = dict(state.get("services") or {})
        snap["alerts"] = list(state.get("alerts") or [])
        snap["last_updated"] = dict(state.get("last_updated") or {})
        snap["weather"] = dict(state.get("weather") or {})
        snap["last_session"] = dict(state.get("last_session") or {})
        snap["orchestra"] = dict(state.get("orchestra") or {})
        snap["orchestra_last_report"] = dict(
            state.get("orchestra_last_report") or {}
        )
        snap["self_status"] = dict(state.get("self_status") or {})
        return snap


# ─── API 路由 ──────────────────────────────────

@app.route("/api/dashboard")
@require_token
def dashboard():
    with state_lock:
        return jsonify(state)


@app.route("/api/status", methods=["POST"])
@require_token
def update_status():
    """接收 Windows CC hooks 上报的状态

    Body: {
      "status": "idle|running|waiting|error|compact-warning",
      "context_percent": 0-100,
      "session_cost_usd": 0.85,
      "session_id": "...",
      "model": "...",
      "round": 12,
      "session_start": true,
      "session_end": true
    }
    """
    data = request.get_json() or {}
    new_status = data.get("status", "idle")
    led_status = None

    with state_lock:
        if new_status != state["cc_status"]:
            state["cc_status"] = new_status
            led_status = new_status

        state["cc_panel"] = _resolve_panel(new_status, state.get("cc_panel", "idle"))

        if "context_percent" in data:
            try:
                pct = max(0, min(100, int(float(data["context_percent"]))))
                state["cc_context_percent"] = pct
                state["cc_context_peak"] = max(
                    int(state.get("cc_context_peak") or 0), pct
                )
            except (TypeError, ValueError):
                pass
        elif new_status == "compact-warning":
            state["cc_context_percent"] = min(
                int(state.get("cc_context_percent") or 0) + 10, 95
            )
            state["cc_context_peak"] = max(
                int(state.get("cc_context_peak") or 0),
                state["cc_context_percent"],
            )

        if "session_cost_usd" in data:
            try:
                state["cc_session_cost_usd"] = float(data["session_cost_usd"])
            except (TypeError, ValueError):
                pass

        if data.get("session_id"):
            state["cc_session_id"] = str(data["session_id"])
        if data.get("model"):
            state["cc_model"] = str(data["model"])

        if "round" in data:
            try:
                state["cc_round"] = max(0, int(data["round"]))
            except (TypeError, ValueError):
                pass
        elif new_status == "running" and data.get("bump_round"):
            state["cc_round"] = int(state.get("cc_round") or 0) + 1

        if data.get("session_start"):
            state["cc_session_start"] = time.time()
            state["cc_round"] = 0
            state["cc_context_percent"] = 0
            state["cc_context_peak"] = 0
            state["cc_session_cost_usd"] = 0.0
            state["cc_model"] = ""

        if data.get("session_end"):
            started = state.get("cc_session_start")
            duration = int(time.time() - started) if started else 0
            state["last_session"] = {
                "cost_usd": float(state.get("cc_session_cost_usd") or 0),
                "duration_sec": duration,
                "context_peak_percent": int(
                    state.get("cc_context_peak")
                    or state.get("cc_context_percent")
                    or 0
                ),
                "round": int(state.get("cc_round") or 0),
                "model": state.get("cc_model") or "",
                "ended_at": time.time(),
            }
            state["cc_session_start"] = None
            # 活跃字段保留到下次 session_start; 面板已因 idle 切走

        state["last_updated"]["status"] = time.time()

    # GPIO / 刷屏均在锁外, 避免 hooks 超时
    if led_status and led:
        try:
            led.set_status(led_status)
        except Exception as e:
            log.warning("LED set_status failed: %s", e)
    _request_eink_refresh()

    return jsonify({"ok": True})


@app.route("/api/orchestra", methods=["POST"])
@require_token
def update_orchestra():
    """接收 Orchestra Broker 状态上报 (subsystem-4)

    Body: {
      "source": "broker|sync",   # 可选, 缺省/非法值按 "broker"
      "broker_health": "up|down|...",
      "queue_len": 3,
      "active_tasks": 1,
      "last_task": "T-20260819-e2e-dsh",
      "last_sync": 1750000000.25,
      "recent_tasks": [
        {"slug": "T-...", "status": "running", "ts": 1750000000.0},
        ...
      ],
      "host": {"load1": 0.3, "mem_pct": 38}   # 设备负载/内存 (逐项校验)
    }
    字段任意子集; 非法字段忽略且不计入 merged。
    recent_tasks 必须为 list, 每项为含 slug/status/ts 的 dict; 非法项丢弃,
    合法后整表替换 (Broker 权威), 仅保留前 8 条。
    host 必须为 dict; load1 (int/float 或 null)、mem_pct (0-100 int 或 null)
    逐项校验, 非法丢弃、合法覆盖; merged 含 "host" 当且仅当至少一项合法。
    """
    data = request.get_json() or {}
    source = data.get("source", "broker")
    if source not in ("broker", "sync"):
        source = "broker"

    merged = []
    with state_lock:
        orch = state["orchestra"]
        for field, value in data.items():
            if field == "source" or field not in orch:
                continue
            if field in ("queue_len", "active_tasks"):
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    log.warning("orchestra: invalid %s=%r ignored", field, value)
                    continue
            elif field == "last_task":
                if not isinstance(value, str) or not value.strip():
                    log.warning("orchestra: invalid last_task=%r ignored", value)
                    continue
            elif field == "last_sync":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    log.warning("orchestra: invalid last_sync=%r ignored", value)
                    continue
            elif field == "broker_health":
                if not isinstance(value, str) or not value.strip():
                    log.warning(
                        "orchestra: invalid broker_health=%r ignored", value
                    )
                    continue
            elif field == "recent_tasks":
                if not isinstance(value, list):
                    log.warning(
                        "orchestra: invalid recent_tasks=%r ignored (not list)",
                        value,
                    )
                    continue
                tasks = []
                for item in value:
                    if not isinstance(item, dict):
                        log.warning(
                            "orchestra: recent_tasks item not dict ignored: %r",
                            item,
                        )
                        continue
                    slug = item.get("slug")
                    status = item.get("status")
                    ts = item.get("ts")
                    if not isinstance(slug, str) or not slug.strip():
                        log.warning(
                            "orchestra: recent_tasks item bad slug ignored: %r",
                            item,
                        )
                        continue
                    if not isinstance(status, str) or not status.strip():
                        log.warning(
                            "orchestra: recent_tasks item bad status ignored: %r",
                            item,
                        )
                        continue
                    if isinstance(ts, bool) or not isinstance(ts, (str, int, float)):
                        log.warning(
                            "orchestra: recent_tasks item bad ts ignored: %r",
                            item,
                        )
                        continue
                    tasks.append({"slug": slug, "status": status, "ts": ts})
                # 整表替换 (Broker 权威), 仅保留前 8 条
                orch[field] = tasks[:8]
                merged.append(field)
                continue
            elif field == "host":
                if not isinstance(value, dict):
                    log.warning(
                        "orchestra: invalid host=%r ignored (not dict)", value
                    )
                    continue
                host = dict(orch.get("host") or {})
                ok = False
                for key in ("load1", "mem_pct"):
                    if key not in value:
                        continue
                    v = value[key]
                    if v is None:
                        host[key] = None
                        ok = True
                    elif key == "load1" and (
                        isinstance(v, (int, float)) and not isinstance(v, bool)
                    ):
                        host[key] = v
                        ok = True
                    elif (
                        key == "mem_pct"
                        and isinstance(v, int)
                        and not isinstance(v, bool)
                        and 0 <= v <= 100
                    ):
                        host[key] = v
                        ok = True
                    else:
                        log.warning(
                            "orchestra: invalid host.%s=%r ignored", key, v
                        )
                if ok:
                    orch["host"] = host
                    merged.append("host")
                continue
            orch[field] = value
            merged.append(field)
        state["orchestra_last_report"][source] = time.time()

    _request_eink_refresh()
    return jsonify({"ok": True, "merged": merged})


@app.route("/health")
def health():
    with state_lock:
        lu = dict(state.get("last_updated") or {})
        svc = dict(state.get("services") or {})
        cc = state.get("cc_status")
        panel = state.get("cc_panel", "idle")
        orch_rep = dict(state.get("orchestra_last_report") or {})
    now = time.time()
    return jsonify({
        "status": "ok",
        "cc_status": cc,
        "cc_panel": panel,
        "services": svc,
        "eink_ready": bool(eink and getattr(eink, "epd", None)),
        "led_ready": led is not None,
        "auth_required": bool(MONITOR_TOKEN),
        "age_seconds": {
            "balance": int(now - lu["balance"]) if lu.get("balance") else None,
            "usage": int(now - lu["usage"]) if lu.get("usage") else None,
            "status": int(now - lu["status"]) if lu.get("status") else None,
            "weather": int(now - lu["weather"]) if lu.get("weather") else None,
            "orchestra_broker": (
                int(now - orch_rep["broker"]) if orch_rep.get("broker") else None
            ),
            "orchestra_sync": (
                int(now - orch_rep["sync"]) if orch_rep.get("sync") else None
            ),
        },
    })


# ─── 启动 ──────────────────────────────────────

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    job_defaults = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 60}

    scheduler.add_job(
        fetch_balance, "interval", seconds=BALANCE_INTERVAL, **job_defaults
    )
    scheduler.add_job(
        _refresh_eink, "interval", seconds=EINK_CHECK_INTERVAL, **job_defaults
    )

    try:
        from usage_scraper import fetch_usage_sync  # noqa: F401

        scheduler.add_job(
            _run_usage_scrape,
            "interval",
            seconds=USAGE_SCRAPE_INTERVAL,
            **job_defaults,
        )
        log.info("Usage scraper scheduled every %ss", USAGE_SCRAPE_INTERVAL)
    except ImportError as e:
        log.warning("Usage scraper not available: %s", e)

    scheduler.add_job(
        _run_weather, "interval", seconds=WEATHER_INTERVAL, **job_defaults
    )
    log.info("Weather scheduled every %ss", WEATHER_INTERVAL)
    scheduler.add_job(
        _run_self_status, "interval", seconds=SELF_STATUS_INTERVAL, **job_defaults
    )
    log.info("Self status scheduled every %ss", SELF_STATUS_INTERVAL)

    scheduler.start()
    _start_eink_worker()
    fetch_balance()
    # 启动时后台拉用量/天气/本机状态, 不阻塞监听端口
    threading.Thread(
        target=_run_usage_scrape, name="boot-usage", daemon=True
    ).start()
    threading.Thread(
        target=_run_weather, name="boot-weather", daemon=True
    ).start()
    threading.Thread(
        target=_run_self_status, name="boot-self-status", daemon=True
    ).start()
    _request_eink_refresh()

    if MONITOR_TOKEN:
        log.info("MONITOR_TOKEN enabled — API requires X-Monitor-Token")
    else:
        log.warning("MONITOR_TOKEN empty — API is open on LAN")

    log.info("Listening on %s:%s", FLASK_HOST, FLASK_PORT)
    try:
        app.run(
            host=FLASK_HOST,
            port=FLASK_PORT,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    finally:
        scheduler.shutdown(wait=False)
        _stop_eink_worker()
        if led:
            led.cleanup()
            log.info("LED cleaned up")
        if eink:
            try:
                eink.sleep()
            except Exception:
                pass
            log.info("E-ink sleeping")
