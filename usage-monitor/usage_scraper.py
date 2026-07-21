"""DeepSeek Platform 用量数据抓取 — Playwright 自动化

抓取策略:
  1. 复用保存的 auth_state.json 恢复登录态
  2. 过期时抛出 LoginExpiredError, 需要手动重新登录
  3. 抓取失败时保留旧数据, 标记服务状态
"""

import asyncio
import json
import time
import subprocess
import sys
from pathlib import Path

from config import (
    DEEPSEEK_PLATFORM_URL, DEEPSEEK_USAGE_URL, AUTH_STATE_FILE,
)


class LoginExpiredError(Exception):
    """登录态过期, 需要交互式重新登录"""
    pass


def fetch_usage_sync(state: dict) -> None:
    """同步包装器, 供 APScheduler 调用"""
    try:
        asyncio.run(_fetch_usage(state))
    except LoginExpiredError:
        print("[usage] Login expired, need interactive re-auth")
        state["services"]["deepseek_platform"] = "login_expired"
    except Exception as e:
        print(f"[usage] Scrape error: {e}")
        state["services"]["deepseek_platform"] = "error"


async def _fetch_usage(state: dict) -> None:
    """异步核心: Playwright 自动化登录并抓取用量数据"""
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
            await page.goto(
                DEEPSEEK_USAGE_URL, wait_until="networkidle", timeout=30000
            )

            # 检查是否被重定向到登录页
            if "login" in page.url.lower():
                await browser.close()
                raise LoginExpiredError("Need interactive login")

            # 等待页面数据渲染
            await page.wait_for_timeout(3000)

            # 提取用量数据
            # 注意: DOM 选择器需要在 DeepSeek Platform 实页上验证调整
            data = await _extract_usage_data(page)
            state["usage"] = data
            state["last_updated"]["usage"] = time.time()
            state["services"]["deepseek_platform"] = "up"

            # 刷新登录态有效期
            await context.storage_state(path=str(AUTH_STATE_FILE))

        finally:
            await browser.close()


async def _extract_usage_data(page) -> dict:
    """从 DeepSeek Platform 页面提取结构化用量数据

    DeepSeek 页面结构可能随时变化, 此函数提供两种提取策略:
      1. 优先从页面内嵌的 JSON/API 响应中解析
      2. 回退到 DOM 文本解析
    """
    result = {
        "period_spending": "0",
        "total_spending": "0",
        "total_requests": 0,
        "total_tokens": 0,
        "models": [],
    }

    # 策略 1: 尝试拦截/读取页面中的 API 数据
    # DeepSeek Platform 是 React SPA, 数据可能在 __NEXT_DATA__ 或
    # 某个 <script> 标签中的 JSON blob 里
    try:
        raw_data = await page.evaluate("""() => {
            // 尝试从 Next.js 水合数据中提取
            const el = document.getElementById('__NEXT_DATA__');
            if (el) return JSON.parse(el.textContent);
            return null;
        }""")
        if raw_data:
            # 根据实际 JSON 结构解析 (待实页验证)
            print(f"[usage] Found __NEXT_DATA__, keys: {list(raw_data.keys())}")
    except Exception:
        pass

    # 策略 2: DOM 文本解析 (回退)
    try:
        dom_data = await page.evaluate("""() => {
            const result = {
                period_spending: '0', total_spending: '0',
                total_requests: 0, total_tokens: 0, models: []
            };

            // 扫描页面文本提取数字
            const text = document.body.innerText;

            // 尝试匹配金额模式: ¥XX.XX
            const cnyPattern = /¥\s*([\d,]+\.?\d*)/g;
            const matches = [...text.matchAll(cnyPattern)];
            // (具体解析逻辑需要根据实页DOM调整)

            return result;
        }""")
        result.update(dom_data)
    except Exception as e:
        print(f"[usage] DOM extraction failed: {e}")

    return result


# ─── 交互式登录 ──────────────────────────────

def login_interactive() -> None:
    """打开浏览器让用户手动登录 DeepSeek Platform, 保存 cookie

    在树莓派上需要 DISPLAY 环境变量 (接显示器或 VNC),
    或无头模式下通过 OAuth 流程完成。
    """
    print("=" * 50)
    print("DeepSeek Platform 登录助手")
    print(f"登录成功后 cookie 保存到: {AUTH_STATE_FILE}")
    print("=" * 50)

    code = f'''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("{DEEPSEEK_PLATFORM_URL}")
        print("请在浏览器中完成登录...")
        # 等待跳转到 usage 页面 (最多等 5 分钟)
        try:
            await page.wait_for_url("**/usage**", timeout=300000)
        except Exception:
            await page.wait_for_timeout(60000)
        await page.context.storage_state(path="{AUTH_STATE_FILE}")
        print("登录态已保存!")
        await browser.close()

asyncio.run(main())
'''

    subprocess.run([sys.executable, "-c", code])
