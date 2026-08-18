"""墨水屏渲染引擎 — 数据 → PIL 灰度位图 → SPI 推送到 Waveshare 5.83"

渲染策略:
  全刷 (display):     数据内容变化 / 每 30min 强制清残影
  局刷 (displayPartial): 仅状态指示器变化
  不刷:               数据未变化 (hash 对比)
"""

import json
import os
import time
import tempfile
import hashlib
from PIL import Image, ImageDraw, ImageFont

from config import (
    EINK_WIDTH, EINK_HEIGHT,
    EINK_FORCE_FULL_REFRESH,
    BALANCE_WARN_THRESHOLD, BALANCE_CRITICAL_THRESHOLD,
    COMPACT_THRESHOLD_TOKENS,
)


class EinkDashboard:
    """管理墨水屏渲染和刷新策略

    用法:
      eink = EinkDashboard()
      eink.init_hardware()          # 连接 SPI 墨水屏 (可选)
      result = eink.render(state)   # 'full' | 'partial' | 'none'
      eink.sleep()                  # 休眠省电
    """

    def __init__(self):
        self.epd = None  # 延迟初始化, 允许无硬件时测试渲染
        self.last_data_hash = ""
        self.last_full_refresh = 0.0
        self.width = EINK_WIDTH
        self.height = EINK_HEIGHT
        self._init_fonts()

    def _init_fonts(self) -> None:
        """加载字体, 降级到 default"""
        try:
            self.font_title = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18
            )
            self.font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
            )
            self.font_medium = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            self.font_normal = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
            )
            self.font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11
            )
        except OSError:
            self.font_title = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_normal = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    # ─── 硬件接口 ──────────────────────────────

    def init_hardware(self) -> None:
        """初始化 Waveshare 5.83" V2 墨水屏 (SPI)"""
        from waveshare_epd import epd5in83_V2
        self.epd = epd5in83_V2.EPD()
        self.epd.init()

    def sleep(self) -> None:
        """墨水屏进入休眠 (省电, 画面保持)"""
        if self.epd:
            self.epd.sleep()

    def clear(self) -> None:
        """强制清屏 (白屏)"""
        if self.epd:
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

    # ─── 主渲染入口 ────────────────────────────

    def render(self, state: dict) -> str:
        """
        渲染仪表盘到位图并推送到墨水屏。

        Returns:
          'full'    - 全屏刷新
          'partial' - 局部刷新
          'none'    - 无变化, 跳过
        """
        data_str = json.dumps(state, sort_keys=True, default=str)
        new_hash = hashlib.md5(data_str.encode()).hexdigest()

        if new_hash == self.last_data_hash:
            return "none"

        image = self._draw(state)
        self.last_data_hash = new_hash
        now = time.time()

        # 无硬件模式: 保存 PNG 用于调试
        if not self.epd:
            preview_path = os.path.join(tempfile.gettempdir(), "eink_preview.png")
            image.save(preview_path)
            return "none"

        # 判断刷新级别
        force_full = (now - self.last_full_refresh) > EINK_FORCE_FULL_REFRESH
        is_initial = not self.last_full_refresh

        if force_full or is_initial:
            self.epd.display(self.epd.getbuffer(image))
            self.last_full_refresh = now
            return "full"
        else:
            self.epd.displayPartial(self.epd.getbuffer(image))
            return "partial"

    # ─── 版面绘制 ──────────────────────────────

    def _draw(self, state: dict) -> Image.Image:
        """绘制完整仪表盘 648×480 灰度位图"""
        img = Image.new("1", (self.width, self.height), 1)  # 1 = white
        draw = ImageDraw.Draw(img)

        self._draw_title_bar(draw, state)

        # 卡片行 1: 余额 + 本期消费
        y = 50
        self._draw_card(draw, 10, y, 310, 80, "充值余额",
                        f"¥ {state['balance'].get('total', '--')}",
                        self._balance_subtitle(state))
        self._draw_card(draw, 330, y, 310, 80, "本期消费",
                        f"¥ {state['usage'].get('period_spending', '--')}",
                        "")

        # 卡片行 2: 累计消费 + 请求次数
        y = 145
        self._draw_card(draw, 10, y, 310, 80, "累计消费",
                        f"¥ {state['usage'].get('total_spending', '--')}",
                        "")
        self._draw_card(draw, 330, y, 310, 80, "API 请求次数",
                        f"{state['usage'].get('total_requests', 0):,}",
                        f"Tokens: {self._fmt_tokens(state['usage'].get('total_tokens', 0))}")

        # 上下文窗口
        y = 240
        self._draw_context_bar(draw, 10, y, self.width - 20, state)

        # 分隔线 + 模型用量
        y = 285
        draw.line([(10, y), (self.width - 10, y)], fill=0)
        self._draw_model_usage(draw, 10, y + 8, self.width - 20, state)

        # 底栏
        y = 420
        self._draw_footer(draw, 10, y, self.width - 20, state)

        return img

    # ─── 子区域绘制 ────────────────────────────

    def _draw_title_bar(self, draw: ImageDraw.Draw, state: dict) -> None:
        """黑底白字标题栏: 标题 + 状态 + 时间"""
        draw.rectangle([(0, 0), (self.width, 35)], fill=0)
        draw.text((10, 8), "DEEPSEEK 用量监控", fill=1, font=self.font_title)

        status_map = {
            "idle": "[ ] 空闲",
            "running": "[*] 运行中",
            "waiting": "[?] 等待",
            "error": "[X] 故障",
        }
        status_text = status_map.get(state.get("cc_status", "idle"), "[ ] --")
        draw.text((280, 8), status_text, fill=1, font=self.font_small)

        time_str = time.strftime("%H:%M", time.localtime())
        draw.text((self.width - 60, 8), time_str, fill=1, font=self.font_small)

    def _draw_card(
        self, draw: ImageDraw.Draw,
        x: int, y: int, w: int, h: int,
        title: str, value: str, subtitle: str,
    ) -> None:
        """通用卡片: 细线边框 + 标题 + 大号数值"""
        draw.rectangle([(x, y), (x + w, y + h)], outline=0)
        draw.text((x + 8, y + 4), title, fill=0, font=self.font_small)
        draw.text((x + 8, y + 22), value, fill=0, font=self.font_large)
        if subtitle:
            draw.text((x + 8, y + 62), subtitle, fill=0, font=self.font_small)

    def _draw_context_bar(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, state: dict
    ) -> None:
        """上下文窗口进度条 + 会话信息"""
        pct = min(state.get("cc_context_percent", 0), 100)
        bar_w = w - 20
        filled = int(bar_w * pct / 100)

        draw.rectangle([(x, y), (x + w, y + 36)], outline=0)
        draw.text((x + 8, y + 2),
                  f"上下文窗口  {pct}%", fill=0, font=self.font_small)

        # 进度条
        bar_y = y + 18
        draw.rectangle([(x + 8, bar_y), (x + 8 + bar_w, bar_y + 10)], outline=0)
        if filled > 0:
            draw.rectangle(
                [(x + 9, bar_y + 1), (x + 8 + filled, bar_y + 9)], fill=0
            )

        # 会话信息
        session_start = state.get("cc_session_start")
        if session_start:
            elapsed = int(time.time() - session_start)
            mins = elapsed // 60
            rnd = state.get("cc_round", 0)
            info = f"会话: {mins}min  第{rnd}轮"
            draw.text((x + w - 200, y + 2), info, fill=0, font=self.font_small)

    def _draw_model_usage(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, state: dict
    ) -> None:
        """模型用量条形图"""
        draw.text((x, y - 2), "模型用量", fill=0, font=self.font_small)
        models = state.get("usage", {}).get("models", [])
        if not models:
            draw.text((x, y + 18), "(暂无数据)", fill=0, font=self.font_small)
            return

        max_tokens = max(m["tokens"] for m in models) if models else 1
        bar_w = w - 260

        for i, model in enumerate(models):
            by = y + 18 + i * 28
            bar_fill = int(bar_w * model["tokens"] / max_tokens)

            draw.text((x + 4, by), model["name"], fill=0, font=self.font_small)
            draw.rectangle(
                [(x + 160, by + 2), (x + 160 + bar_w, by + 16)], outline=0
            )
            if bar_fill > 0:
                draw.rectangle(
                    [(x + 161, by + 3), (x + 160 + bar_fill, by + 15)], fill=0
                )

            info = f"{model['requests']:,}次  {self._fmt_tokens(model['tokens'])}"
            draw.text((x + 160 + bar_w + 6, by + 1), info,
                      fill=0, font=self.font_small)

    def _draw_footer(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, state: dict
    ) -> None:
        """底栏: 更新时间 + 延迟 + 服务健康"""
        last_bal = state.get("last_updated", {}).get("balance", 0)
        if last_bal:
            ago = int(time.time() - last_bal)
            update = f"更新: {ago}s前" if ago < 120 else f"更新: {ago // 60}min前"
        else:
            update = "更新: --"
        draw.text((x, y), update, fill=0, font=self.font_small)

        latency = state.get("network_latency_ms", 0)
        draw.text((x + 130, y), f"延迟: {latency}ms", fill=0, font=self.font_small)

        # 服务健康行
        svc = state.get("services", {})
        parts = []
        for svc_name in ["deepseek_api", "deepseek_platform"]:
            sv = svc.get(svc_name, "unknown")
            icon = "OK" if sv == "up" else ("ERR" if sv.startswith("error") else "--")
            parts.append(f"{svc_name}: {icon}")
        draw.text((x, y + 16), " | ".join(parts), fill=0, font=self.font_small)

    # ─── 格式化辅助 ────────────────────────────

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.0f}M"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)

    def _balance_subtitle(self, state: dict) -> str:
        bal = state.get("balance", {})
        if not bal.get("is_available", True):
            return "[!] 余额不足, API 不可用"
        total = float(bal.get("total", 0))
        if total < BALANCE_CRITICAL_THRESHOLD:
            return "[!] 余额严重不足"
        if total < BALANCE_WARN_THRESHOLD:
            return "[!] 余额偏低"
        return "预警已开启"
