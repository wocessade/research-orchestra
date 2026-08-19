"""DeepSeek Platform 用量数据抓取

策略:
  1. 优先用 auth_state.json 里的 cookie/token 调 platform REST
     ( /api/v0/usage/cost , /api/v0/usage/amount )
  2. REST 成功即接受 (含真·零用量月份), 不再靠「数字>0」判空
  3. Playwright 回退默认关闭 (ENABLE_PLAYWRIGHT_FALLBACK=1 才启用)
  4. 登录过期抛 LoginExpiredError — 在 Pi 上跑 login_interactive()
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

from config import (
    AUTH_STATE_FILE,
    DEEPSEEK_PLATFORM_URL,
    DEEPSEEK_USAGE_URL,
    ENABLE_PLAYWRIGHT_FALLBACK,
)

USAGE_COST_URL = f"{DEEPSEEK_PLATFORM_URL.rstrip('/')}/api/v0/usage/cost"
USAGE_AMOUNT_URL = f"{DEEPSEEK_PLATFORM_URL.rstrip('/')}/api/v0/usage/amount"


class LoginExpiredError(Exception):
    """登录态过期, 需要交互式重新登录"""


def scrape_usage() -> dict:
    """网络 I/O 在调用方锁外执行。返回结果 dict, 不写全局 state。

    成功: {"ok": True, "usage": {...}, "service": "up"}
    失败: {"ok": False, "service": "login_expired"|"error", "error": "..."}
    """
    try:
        data = _scrape_usage_data()
        return {"ok": True, "usage": data, "service": "up"}
    except LoginExpiredError as e:
        print(f"[usage] Login expired: {e}", flush=True)
        return {"ok": False, "service": "login_expired", "error": str(e)}
    except Exception as e:
        print(f"[usage] Scrape error: {e}", flush=True)
        return {"ok": False, "service": "error", "error": str(e)}


def fetch_usage_sync(state: dict) -> None:
    """同步包装器 (兼容旧调用): 在已持有的 state 上原地更新。"""
    result = scrape_usage()
    if result.get("ok"):
        _apply_usage(state, result["usage"])
    else:
        state["services"]["deepseek_platform"] = result.get("service", "error")


def _scrape_usage_data() -> dict:
    auth_path = Path(AUTH_STATE_FILE)
    if not auth_path.is_file():
        raise LoginExpiredError(f"Missing {auth_path} — run login_interactive()")

    # 1) cookie + REST (轻量); 成功即接受, 含零用量
    try:
        data = _fetch_via_cookies(auth_path)
        print("[usage] OK via platform REST cookies", flush=True)
        return data
    except LoginExpiredError:
        raise
    except Exception as e:
        print(f"[usage] REST path failed ({e})", flush=True)
        if not ENABLE_PLAYWRIGHT_FALLBACK:
            raise RuntimeError(
                f"REST failed and Playwright fallback disabled: {e}"
            ) from e

    # 2) Playwright + 网络拦截 (可选)
    print("[usage] Falling back to Playwright", flush=True)
    data = asyncio.run(_fetch_via_playwright(auth_path))
    print("[usage] OK via Playwright intercept", flush=True)
    return data


def _apply_usage(state: dict, data: dict) -> None:
    state["usage"] = data
    state["last_updated"]["usage"] = time.time()
    state["services"]["deepseek_platform"] = "up"


# ─── cookie → REST ────────────────────────────

def _load_auth_state(auth_path: Path) -> dict:
    return json.loads(auth_path.read_text(encoding="utf-8"))


def _extract_user_token(raw: dict) -> str | None:
    """DeepSeek Platform 登录态在 localStorage.userToken, 不在 cookie。"""
    for origin in raw.get("origins") or []:
        for item in origin.get("localStorage") or []:
            if item.get("name") != "userToken":
                continue
            val = item.get("value") or ""
            try:
                parsed = json.loads(val)
                token = parsed.get("value") if isinstance(parsed, dict) else val
            except json.JSONDecodeError:
                token = val
            if token:
                return str(token)
    return None


def _load_cookie_jar(raw: dict) -> requests.cookies.RequestsCookieJar:
    jar = requests.cookies.RequestsCookieJar()
    for c in raw.get("cookies", []):
        jar.set(
            c["name"],
            c["value"],
            domain=c.get("domain") or "platform.deepseek.com",
            path=c.get("path") or "/",
        )
    return jar


def _fetch_via_cookies(auth_path: Path) -> dict:
    raw = _load_auth_state(auth_path)
    token = _extract_user_token(raw)
    jar = _load_cookie_jar(raw)
    if not token and not jar:
        raise LoginExpiredError("auth_state.json has no userToken/cookies")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": DEEPSEEK_USAGE_URL,
        "Origin": DEEPSEEK_PLATFORM_URL.rstrip("/"),
    }
    if token:
        # Platform 控制台常用 Bearer userToken
        headers["Authorization"] = f"Bearer {token}"

    session = requests.Session()
    session.cookies = jar
    session.headers.update(headers)

    # Platform API 要求 query: month + year (数字)
    today = date.today()
    params = {"month": today.month, "year": today.year}
    cost_json = _get_json(session, USAGE_COST_URL, params=params)
    amount_json = _get_json(session, USAGE_AMOUNT_URL, params=params)
    return _normalize_usage_payloads(cost_json, amount_json)


def _get_json(session: requests.Session, url: str, params: dict | None = None) -> Any:
    resp = session.get(url, params=params, timeout=20)
    if resp.status_code in (401, 403):
        raise LoginExpiredError(f"HTTP {resp.status_code} from {url}")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} from {url}: {resp.text[:200]}")
    # Cloudflare / HTML block
    ctype = resp.headers.get("content-type", "")
    if "json" not in ctype and resp.text.lstrip().startswith("<"):
        raise RuntimeError(f"Non-JSON response from {url}")
    data = resp.json()
    if isinstance(data, dict):
        code = data.get("code")
        if code not in (None, 0, "0", 200):
            msg = data.get("msg") or data.get("message") or str(code)
            if str(code) in ("40003", "401", "403") or "auth" in str(msg).lower():
                raise LoginExpiredError(msg)
            raise RuntimeError(f"API error {code}: {msg}")
    return data


# ─── Playwright fallback ──────────────────────

async def _fetch_via_playwright(auth_path: Path) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=str(auth_path),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        try:
            await page.goto(DEEPSEEK_USAGE_URL, wait_until="domcontentloaded", timeout=45000)
            if "login" in page.url.lower():
                raise LoginExpiredError("Redirected to login")
            # 同域 fetch, 复用浏览器 cookie
            today = date.today()
            cost_json, amount_json = await page.evaluate(
                """async ([month, year]) => {
                    async function get(path) {
                        const r = await fetch(
                          `${path}?month=${month}&year=${year}`,
                          { credentials: 'include' }
                        );
                        if (!r.ok) return { __http: r.status };
                        try { return await r.json(); } catch (e) { return { __error: String(e) }; }
                    }
                    return await Promise.all([
                        get('/api/v0/usage/cost'),
                        get('/api/v0/usage/amount'),
                    ]);
                }""",
                [today.month, today.year],
            )
            await context.storage_state(path=str(auth_path))
        finally:
            await browser.close()

    for payload, label in ((cost_json, "cost"), (amount_json, "amount")):
        if isinstance(payload, dict) and payload.get("__http") in (401, 403):
            raise LoginExpiredError(f"Playwright fetch {label} HTTP {payload['__http']}")

    return _normalize_usage_payloads(cost_json, amount_json)


# ─── 归一化各种 JSON 形状 ─────────────────────

def _normalize_usage_payloads(cost_json: Any, amount_json: Any) -> dict:
    """解析 platform.deepseek.com /api/v0/usage/{cost,amount} 响应."""
    result = {
        "period_spending": "0",
        "total_spending": "0",
        "total_requests": 0,
        "total_tokens": 0,
        "models": [],
    }

    cost_models = _biz_total_rows(cost_json)
    amount_models = _biz_total_rows(amount_json)

    spending = 0.0
    for row in cost_models:
        for u in row.get("usage") or []:
            spending += _as_float(u.get("amount"))
    if spending > 0:
        result["total_spending"] = _fmt_money(spending)
        result["period_spending"] = _fmt_money(spending)

    tokens = 0
    requests_n = 0
    models: list[dict] = []
    for row in amount_models:
        name = str(row.get("model") or "unknown")
        m_tokens = 0
        m_req = 0
        for u in row.get("usage") or []:
            typ = str(u.get("type") or "").upper()
            amt = _as_float(u.get("amount"))
            if typ == "REQUEST":
                m_req += int(amt)
            elif "TOKEN" in typ:
                m_tokens += int(amt)
        tokens += m_tokens
        requests_n += m_req
        if m_tokens or m_req:
            models.append({
                "name": name,
                "tokens": m_tokens,
                "requests": m_req,
            })

    result["total_tokens"] = tokens
    result["total_requests"] = requests_n
    result["models"] = sorted(models, key=lambda m: m["tokens"], reverse=True)[:6]
    return result


def _biz_total_rows(payload: Any) -> list[dict]:
    """从 {data:{biz_data:...}} 取出 total 模型列表."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return []
    biz = data.get("biz_data", data)
    # cost: biz_data = [{total, days, currency}]
    # amount: biz_data = {total, days}
    if isinstance(biz, list):
        rows: list[dict] = []
        for item in biz:
            if isinstance(item, dict) and isinstance(item.get("total"), list):
                rows.extend(item["total"])
        return rows
    if isinstance(biz, dict) and isinstance(biz.get("total"), list):
        return biz["total"]
    return []


def _as_float(v: Any) -> float:
    try:
        return float(str(v).replace(",", "").replace("¥", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _fmt_money(v: float) -> str:
    return f"{v:.2f}"


# ─── 交互式登录 ──────────────────────────────

def login_interactive() -> None:
    """打开浏览器手动登录, 保存 cookie 到 AUTH_STATE_FILE。

    浏览器会一直开着, 直到你在终端按回车 — 方便扫码登录。
    """
    auth_path = Path(AUTH_STATE_FILE)
    print("=" * 50, flush=True)
    print("DeepSeek Platform 登录助手", flush=True)
    print(f"cookie 将保存到: {auth_path}", flush=True)
    print("=" * 50, flush=True)
    print("1. 浏览器打开后请扫码/登录", flush=True)
    print("2. 尽量点进「用量 / Usage」页面", flush=True)
    print("3. 回到本终端, 按回车才会保存并关闭", flush=True)
    print("=" * 50, flush=True)

    async def _main() -> None:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(DEEPSEEK_PLATFORM_URL, wait_until="domcontentloaded")

            # 关键: 等用户确认, 不要靠 URL 误判
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: input("\n>>> 登录完成后, 在这里按回车保存 cookie... "),
            )

            # 尽量打开用量页, 确认 cookie 可用
            try:
                await page.goto(DEEPSEEK_USAGE_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
            except Exception as e:
                print(f"[login] 打开用量页失败 (仍会保存当前 cookie): {e}", flush=True)

            if "login" in page.url.lower():
                print(
                    "[login] 警告: 当前仍在登录页, cookie 可能无效。"
                    "请确认已登录后再跑一次 login。",
                    flush=True,
                )

            await context.storage_state(path=str(auth_path))
            n_cookies = len(json.loads(auth_path.read_text(encoding="utf-8")).get("cookies", []))
            print(f"登录态已保存: {auth_path}  (cookies={n_cookies})", flush=True)
            await browser.close()

    asyncio.run(_main())


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        login_interactive()
    else:
        result = scrape_usage()
        print(json.dumps(result, ensure_ascii=False, indent=2))
