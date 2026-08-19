"""墨水屏渲染引擎 — 数据 → PIL 灰度位图 → SPI 推送到 Waveshare 3.97"

渲染策略:
  全刷 (display_Base): 面板切换 / 余额用量变化 / 首次 / 30min 强制清残影
  局刷 (全幅波形):    同面板内时间/状态/会话字段变化
  不刷:              无变化

双面板 (见 docs/dual_panel.md):
  active — CC running/waiting: DeepSeek 四卡 + 模型用量
  idle   — 天气 + DeepSeek 速览/明细 + 日期/健康
  (SHOW_CC_CONTEXT=False 时隐藏上下文%/Claude 会话区; 见 config)

局刷要点:
  - 使用全幅 display_Partial (局刷波形 0xFF, ~0.6s, 无闪烁)。
    多 zone 裁剪窗口在本面板上会与 init 的 Y 寻址冲突。
  - getbuffer_Part 会反转字节; 须用 _invert_1bit 预抵消
    (不可对 mode='1' 直接 ImageOps.invert)。
"""

import json
import os
import sys
import time
import tempfile
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import (
    EINK_WIDTH, EINK_HEIGHT,
    EINK_FORCE_FULL_REFRESH,
    BALANCE_WARN_THRESHOLD, BALANCE_CRITICAL_THRESHOLD,
    SHOW_CC_CONTEXT,
    SHOW_ORCHESTRA, ORCHESTRA_ROTATE_SEC, ORCHESTRA_STALE_SEC,
)

# ─── 版面常量 (与 _draw() 布局严格对应) ───────────
# 800×480; 无上下文区时卡片加高、模型条下移占满中下区

TITLE_BAR_H = 52
CARD_W = 380
CARD_LEFT_X = 15
CARD_RIGHT_X = 405

if SHOW_CC_CONTEXT:
    # 原双面板: 四卡 + 上下文条 + 会话行 + 模型条
    CARD_H = 108
    CARD_ROW1_Y = 66
    CARD_ROW2_Y = 186
    IDLE_CARD_H = 130
    CONTEXT_Y = 306
    CONTEXT_H = 42
    SEPARATOR_Y = 354
    MODEL_Y = 362
    FOOTER_Y = 428
else:
    # 无上下文: 四卡加高, 模型用量独占中下, 底栏贴底
    CARD_H = 128
    CARD_ROW1_Y = 62
    CARD_ROW2_Y = 202
    IDLE_CARD_H = 150
    IDLE_ROW2_Y = 228  # 闲置第二行 (DeepSeek 明细)
    IDLE_ROW2_H = 120
    CONTEXT_Y = 0       # unused when SHOW_CC_CONTEXT=False
    CONTEXT_H = 0
    SEPARATOR_Y = 340
    MODEL_Y = 348
    FOOTER_Y = 430

FOOTER_H = 52

# True: 启用局刷波形 (全幅写入, 避免多 zone 窗口错位)
PARTIAL_REFRESH_ENABLED = True

# ─── 中文字体候选路径 ────────────────────────

_CJK_FONT_PATHS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    # Windows 回退 (快照 CLI 预览用); Linux 路径优先, 不受影响
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


class EinkDashboard:
    """管理墨水屏渲染和刷新策略

    用法:
      eink = EinkDashboard()
      eink.init_hardware()
      result = eink.render(state)   # 'full' | 'none'
      eink.sleep()
    """

    def __init__(self):
        self.epd = None
        self._last_data_hash = ""
        self._last_display_hash = ""
        self._last_panel = ""
        self._last_full_refresh = 0.0
        self._partial_used = False
        self._last_frame_buf = None  # 上一帧 getbuffer 数据, 局刷 reset 后写回双 RAM
        self.width = EINK_WIDTH
        self.height = EINK_HEIGHT
        self._init_fonts()

    def _init_fonts(self) -> None:
        """加载字体: CJK 优先 → DejaVu → PIL default"""
        cjk_font = None
        for path in _CJK_FONT_PATHS:
            if os.path.exists(path):
                cjk_font = path
                break

        if cjk_font:
            try:
                self.font_title = ImageFont.truetype(cjk_font, 24)
                self.font_large = ImageFont.truetype(cjk_font, 46)
                self.font_medium = ImageFont.truetype(cjk_font, 20)
                self.font_normal = ImageFont.truetype(cjk_font, 18)
                self.font_small = ImageFont.truetype(cjk_font, 15)
                print(f"[eink] Using CJK font: {cjk_font}", flush=True)
                return
            except OSError as e:
                print(f"[eink] CJK font load failed ({e})")

        try:
            self.font_title = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
            self.font_medium = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            self.font_normal = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            self.font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
            print("[eink] Using DejaVu fonts (no CJK)")
        except OSError:
            self.font_title = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_normal = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            print("[eink] Using PIL default font")

    # ─── 硬件接口 ──────────────────────────────

    def init_hardware(self) -> None:
        from waveshare_epd import epd3in97
        self.epd = epd3in97.EPD()
        self.epd.init()

    def sleep(self) -> None:
        if self.epd:
            self.epd.sleep()

    def clear(self) -> None:
        if self.epd:
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()

    # ─── Hash 计算 ────────────────────────────

    @staticmethod
    def _resolve_panel(state: dict) -> str:
        panel = state.get("cc_panel")
        if panel in ("idle", "active"):
            return panel
        status = state.get("cc_status", "idle")
        return "active" if status in ("running", "waiting") else "idle"

    @classmethod
    def _resolve_display_panel(cls, state: dict, now=None) -> str:
        """展示面板 = 基面板; 仅当基面板 idle 且 SHOW_ORCHESTRA 且 broker
        已有上报时, 按 ORCHESTRA_ROTATE_SEC 时间桶奇偶轮换到 orchestra。

        now 注入用于测试; 同桶内确定性, 跨桶翻转触发全刷。
        """
        panel = cls._resolve_panel(state)
        if panel != "idle" or not SHOW_ORCHESTRA:
            return panel
        last_report = state.get("orchestra_last_report") or {}
        if not last_report.get("broker"):
            return panel
        if now is None:
            now = time.time()
        return "orchestra" if int(now // ORCHESTRA_ROTATE_SEC) % 2 else "idle"

    @staticmethod
    def _compute_data_hash(state: dict) -> str:
        """数据关键字段 hash — 变化时需全刷清残影。

        不含 services: 平台状态抖动不应触发全刷。
        """
        data_fields = {
            "balance": state.get("balance", {}),
            "usage": state.get("usage", {}),
            "alerts": state.get("alerts", []),
            "weather": state.get("weather", {}),
        }
        # 上下文展示开启时, 上一会话变更也触发全刷
        if SHOW_CC_CONTEXT:
            data_fields["last_session"] = state.get("last_session", {})
        return hashlib.md5(
            json.dumps(data_fields, sort_keys=True, default=str).encode()
        ).hexdigest()

    @classmethod
    def _compute_display_hash(cls, state: dict, now=None) -> str:
        """全部展示字段 hash (含时间) — 决定是否需要局刷。

        不含 last_updated (每 60s 余额时间戳会无意义推刷);
        services 保留以便底栏健康状态可局刷更新。
        orchestra 纳入: 内容变化走局刷, 面板轮换由 panel 键 (桶号) 触发全刷。
        """
        if now is None:
            now = time.time()
        display_fields = {
            "panel": cls._resolve_display_panel(state, now),
            "balance": state.get("balance", {}),
            "usage": state.get("usage", {}),
            "alerts": state.get("alerts", []),
            "services": state.get("services", {}),
            "weather": state.get("weather", {}),
            "cc_status": state.get("cc_status", "idle"),
            "cc_model": state.get("cc_model", ""),
            "orchestra": state.get("orchestra", {}),
            "orchestra_last_report": state.get("orchestra_last_report", {}),
            "_time_minute": time.strftime("%H:%M"),
            "_date": time.strftime("%Y-%m-%d"),
        }
        # 关闭上下文 UI 时不把 cc_context_* / last_session 计入 hash,
        # 避免 hooks 仍上报时触发无意义局刷
        if SHOW_CC_CONTEXT:
            display_fields.update({
                "last_session": state.get("last_session", {}),
                "cc_context_percent": state.get("cc_context_percent", 0),
                "cc_context_peak": state.get("cc_context_peak", 0),
                "cc_round": state.get("cc_round", 0),
                "cc_session_start": state.get("cc_session_start"),
                "cc_session_cost_usd": state.get("cc_session_cost_usd", 0),
            })
        return hashlib.md5(
            json.dumps(display_fields, sort_keys=True, default=str).encode()
        ).hexdigest()

    # ─── 主渲染入口 ────────────────────────────

    def render(self, state: dict) -> str:
        """渲染仪表盘并推送到墨水屏。

        Returns: 'full' | 'partial' | 'none'
        硬件异常向上抛出, 由 app 层 worker 捕获并 re-init。
        """
        now = time.time()
        panel = self._resolve_display_panel(state, now)
        data_hash = self._compute_data_hash(state)
        display_hash = self._compute_display_hash(state, now)

        if display_hash == self._last_display_hash:
            return "none"

        image = self._draw(state, panel)
        # 先算好帧; 推屏失败时不推进 hash, 以便下次重试

        if not self.epd:
            preview_path = os.path.join(tempfile.gettempdir(), "eink_preview.png")
            image.save(preview_path)
            self._last_display_hash = display_hash
            self._last_data_hash = data_hash
            self._last_panel = panel
            return "none"

        force_full = (now - self._last_full_refresh) > EINK_FORCE_FULL_REFRESH
        is_initial = not self._last_full_refresh
        data_changed = data_hash != self._last_data_hash
        panel_changed = bool(self._last_panel) and panel != self._last_panel

        try:
            if is_initial or data_changed or force_full or panel_changed:
                if self._partial_used:
                    self.epd.init()
                    self._partial_used = False
                frame = self.epd.getbuffer(image)
                self.epd.display_Base(frame)
                self._last_frame_buf = bytes(frame)
                self._last_full_refresh = now
                self._last_data_hash = data_hash
                self._last_panel = panel
                self._last_display_hash = display_hash
                print(
                    f"[eink] FULL refresh (init={is_initial} data={data_changed} "
                    f"force={force_full} panel={panel_changed} → {panel})",
                    flush=True,
                )
                return "full"
            else:
                if PARTIAL_REFRESH_ENABLED:
                    try:
                        self._refresh_partial(image)
                        self._partial_used = True
                        self._last_panel = panel
                        self._last_display_hash = display_hash
                        print("[eink] PARTIAL refresh (full-frame waveform)", flush=True)
                        return "partial"
                    except Exception as e:
                        print(f"[eink] Partial failed, fallback FULL: {e}", flush=True)
                        if self._partial_used:
                            self.epd.init()
                            self._partial_used = False
                        frame = self.epd.getbuffer(image)
                        self.epd.display_Base(frame)
                        self._last_frame_buf = bytes(frame)
                        self._last_full_refresh = now
                        self._last_data_hash = data_hash
                        self._last_panel = panel
                        self._last_display_hash = display_hash
                        return "full"
                else:
                    frame = self.epd.getbuffer(image)
                    self.epd.display_Base(frame)
                    self._last_frame_buf = bytes(frame)
                    self._last_full_refresh = now
                    self._last_data_hash = data_hash
                    self._last_panel = panel
                    self._last_display_hash = display_hash
                    print("[eink] FULL refresh (partial disabled, fallback)", flush=True)
                    return "full"
        except Exception:
            # 不推进 hash, 下次可重试同一帧
            raise

    # ─── 局刷 (全幅窗口 + 局刷波形) ───────────

    @staticmethod
    def _invert_1bit(img: Image.Image) -> Image.Image:
        """可靠的 1bit 反色. mode='1' 上直接 ImageOps.invert 会破坏位图."""
        return ImageOps.invert(img.convert("L")).convert("1")

    def _refresh_partial(self, full_image: Image.Image) -> None:
        """全幅局刷: invert → getbuffer_Part → display_Partial(0,0,W,H)

        实机验证 (方案 C): 无黑条、无错位。局刷波形只驱动变化像素,
        视觉上接近区域更新, 且避开多 zone 窗口的 Y 映射问题。
        """
        epd = self.epd
        inverted = self._invert_1bit(full_image)
        buf = epd.getbuffer_Part(inverted, epd.width, epd.height)
        epd.display_Partial(buf, 0, 0, epd.width, epd.height)
        self._last_frame_buf = bytes(epd.getbuffer(full_image))

    # ─── 版面绘制 ──────────────────────────────

    def _draw(self, state: dict, panel=None) -> Image.Image:
        """绘制完整仪表盘 800×480 灰度位图"""
        panel = panel or self._resolve_display_panel(state)
        img = Image.new("1", (self.width, self.height), 1)
        draw = ImageDraw.Draw(img)
        if panel == "idle":
            self._draw_idle(draw, state)
        elif panel == "orchestra":
            self._draw_orchestra(draw, state)
        else:
            self._draw_active(draw, state)
        return img

    def _draw_active(self, draw: ImageDraw.Draw, state: dict) -> None:
        """活跃面板: DeepSeek 四卡 + 模型用量 (+ 可选上下文/会话)"""
        self._draw_title_bar(draw, state, show_date=False)

        self._draw_card(
            draw, CARD_LEFT_X, CARD_ROW1_Y, CARD_W, CARD_H,
            "充值余额",
            f"¥ {state['balance'].get('total', '--')}",
            self._balance_subtitle(state),
        )
        self._draw_card(
            draw, CARD_RIGHT_X, CARD_ROW1_Y, CARD_W, CARD_H,
            "本期消费",
            f"¥ {state['usage'].get('period_spending', '--')}",
            "",
        )
        self._draw_card(
            draw, CARD_LEFT_X, CARD_ROW2_Y, CARD_W, CARD_H,
            "累计消费",
            f"¥ {state['usage'].get('total_spending', '--')}",
            "",
        )
        self._draw_card(
            draw, CARD_RIGHT_X, CARD_ROW2_Y, CARD_W, CARD_H,
            "API 请求次数",
            f"{state['usage'].get('total_requests', 0):,}",
            f"Tokens: {self._fmt_tokens(state['usage'].get('total_tokens', 0))}",
        )

        # --- 上下文检测 UI (恢复: config.SHOW_CC_CONTEXT = True) ---
        if SHOW_CC_CONTEXT:
            self._draw_context_bar(draw, 15, CONTEXT_Y, self.width - 30, state)
            draw.line([(15, SEPARATOR_Y), (self.width - 15, SEPARATOR_Y)], fill=0)
            self._draw_model_usage(draw, 15, MODEL_Y, self.width - 30, state)
            self._draw_session_line(draw, 15, FOOTER_Y - 28, state)
        else:
            draw.line([(15, SEPARATOR_Y), (self.width - 15, SEPARATOR_Y)], fill=0)
            self._draw_model_usage(
                draw, 15, MODEL_Y, self.width - 30, state, max_models=2, row_h=32
            )

        self._draw_footer(draw, 15, FOOTER_Y, self.width - 30, state)

    def _draw_idle(self, draw: ImageDraw.Draw, state: dict) -> None:
        """闲置面板: 天气 + DeepSeek; 可选上一会话 / 否则明细卡"""
        self._draw_title_bar(draw, state, show_date=True)

        # 天气大卡 (左) + DeepSeek 速览 (右)
        wthr = state.get("weather") or {}
        city = wthr.get("city") or "南京"
        temp = wthr.get("temp_c", "--")
        desc = wthr.get("desc", "--")
        feels = wthr.get("feels_c", "--")
        hum = wthr.get("humidity", "--")
        wind = wthr.get("wind_kmph", "--")
        self._draw_card(
            draw, CARD_LEFT_X, CARD_ROW1_Y, CARD_W, IDLE_CARD_H,
            f"{city} 天气",
            f"{temp}°C",
            f"{desc}  体感{feels}°  湿度{hum}%  风{wind}km/h",
        )

        bal = state.get("balance") or {}
        usage = state.get("usage") or {}
        self._draw_card(
            draw, CARD_RIGHT_X, CARD_ROW1_Y, CARD_W, IDLE_CARD_H,
            "DeepSeek 速览",
            f"¥ {bal.get('total', '--')}",
            (
                f"本期 ¥{usage.get('period_spending', '--')}  "
                f"请求 {usage.get('total_requests', 0):,}"
            ),
        )

        if SHOW_CC_CONTEXT:
            # --- 上一会话 (Claude 上下文摘要; 恢复见 SHOW_CC_CONTEXT) ---
            self._draw_last_session(draw, state)
        else:
            # 第二行: 累计消费 + Tokens / 模型用量占满原「上一会话」空间
            self._draw_card(
                draw, CARD_LEFT_X, IDLE_ROW2_Y, CARD_W, IDLE_ROW2_H,
                "累计消费",
                f"¥ {usage.get('total_spending', '--')}",
                self._balance_subtitle(state),
            )
            self._draw_card(
                draw, CARD_RIGHT_X, IDLE_ROW2_Y, CARD_W, IDLE_ROW2_H,
                "用量 Tokens",
                self._fmt_tokens(usage.get("total_tokens", 0)),
                f"请求 {usage.get('total_requests', 0):,} 次",
            )

        self._draw_footer(draw, 15, FOOTER_Y, self.width - 30, state)

    def _draw_orchestra(self, draw: ImageDraw.Draw, state: dict) -> None:
        """Orchestra 任务面板: Broker 健康 + 任务队列 + 活跃任务 + 最近任务

        四卡复用 active 面板布局 (SHOW_CC_CONTEXT=False 分支); 中下区留空,
        仅 标题栏 + 四卡 + 底栏。
        """
        self._draw_title_bar(draw, state, show_date=True)

        orch = state.get("orchestra") or {}
        rep = state.get("orchestra_last_report") or {}
        now = time.time()

        # 卡1: Broker 健康 — 新鲜度推导 (无上报 "--"; 超阈值 "离线")
        broker_ts = rep.get("broker") or 0
        if not broker_ts:
            health_value, health_sub = "--", ""
        else:
            age = now - broker_ts
            if age <= ORCHESTRA_STALE_SEC:
                health = orch.get("broker_health") or "unknown"
                if health == "ok":
                    health_value = "OK"
                elif health == "unknown":
                    health_value = "--"
                else:
                    health_value = health
            else:
                health_value = "离线"
            health_sub = self._fmt_ago(age)
        self._draw_card(
            draw, CARD_LEFT_X, CARD_ROW1_Y, CARD_W, CARD_H,
            "Broker 健康", health_value, health_sub,
        )

        # 卡2: 任务队列
        queue_len = orch.get("queue_len")
        active = orch.get("active_tasks")
        self._draw_card(
            draw, CARD_RIGHT_X, CARD_ROW1_Y, CARD_W, CARD_H,
            "任务队列",
            "--" if queue_len is None else str(queue_len),
            "活跃 --" if active is None else f"活跃 {active}",
        )

        # 卡3: 活跃任务
        self._draw_card(
            draw, CARD_LEFT_X, CARD_ROW2_Y, CARD_W, CARD_H,
            "活跃任务",
            "--" if active is None else str(active),
            "",
        )

        # 卡4: 最近任务 (slug 过长截断防溢出卡片)
        raw = orch.get("last_task")
        if raw is None or not str(raw).strip():
            task_value = "--"
        else:
            task_value = self._truncate_to_fit(
                str(raw).strip(), self.font_large, CARD_W - 20
            )
        sync_ts = rep.get("sync") or orch.get("last_sync") or 0
        sync_sub = (
            "同步 --" if not sync_ts else f"同步 {self._fmt_ago(now - sync_ts)}"
        )
        self._draw_card(
            draw, CARD_RIGHT_X, CARD_ROW2_Y, CARD_W, CARD_H,
            "最近任务", task_value, sync_sub,
        )

        self._draw_footer(draw, 15, FOOTER_Y, self.width - 30, state)

    def _draw_last_session(self, draw: ImageDraw.Draw, state: dict) -> None:
        """闲置面板: 上一会话 Claude 摘要 (仅 SHOW_CC_CONTEXT=True)"""
        last = state.get("last_session") or {}
        y_sess = CARD_ROW1_Y + IDLE_CARD_H + 18
        draw.rectangle(
            [(15, y_sess), (self.width - 15, y_sess + 110)], outline=0
        )
        draw.text((25, y_sess + 8), "上一会话 (Claude)", fill=0, font=self.font_medium)
        if last:
            cost = float(last.get("cost_usd") or 0)
            dur = int(last.get("duration_sec") or 0)
            peak = int(last.get("context_peak_percent") or 0)
            rnd = int(last.get("round") or 0)
            model = last.get("model") or ""
            draw.text(
                (25, y_sess + 40),
                f"$ {cost:.2f}",
                fill=0,
                font=self.font_large,
            )
            draw.text(
                (280, y_sess + 50),
                f"{self._fmt_duration(dur)}  峰值上下文 {peak}%  第{rnd}轮",
                fill=0,
                font=self.font_normal,
            )
            if model:
                draw.text(
                    (25, y_sess + 88),
                    f"模型: {model}",
                    fill=0,
                    font=self.font_small,
                )
        else:
            draw.text(
                (25, y_sess + 48),
                "(尚无结束的会话)",
                fill=0,
                font=self.font_normal,
            )

    # ─── 子区域绘制 ────────────────────────────

    def _draw_title_bar(
        self, draw: ImageDraw.Draw, state: dict, show_date: bool = False
    ) -> None:
        """黑底白字标题栏 (y: 0 - TITLE_BAR_H)"""
        draw.rectangle([(0, 0), (self.width, TITLE_BAR_H)], fill=0)
        draw.text((12, 12), "DEEPSEEK", fill=1, font=self.font_title)

        status_map = {
            "idle": "[ ] 空闲",
            "running": "[*] 运行中",
            "waiting": "[?] 等待",
            "error": "[X] 故障",
            "compact-warning": "[!] 上下文",
        }
        status_text = status_map.get(state.get("cc_status", "idle"), "[ ] --")
        # 状态字放大, 与标题同级
        draw.text((175, 12), status_text, fill=1, font=self.font_title)

        if show_date:
            weekdays = "一二三四五六日"
            wd = weekdays[time.localtime().tm_wday]
            date_str = time.strftime(f"%m/%d 周{wd}")
            draw.text((360, 12), date_str, fill=1, font=self.font_title)

        time_str = time.strftime("%H:%M", time.localtime())
        draw.text((self.width - 90, 12), time_str, fill=1, font=self.font_title)

    def _draw_card(
        self, draw: ImageDraw.Draw,
        x: int, y: int, w: int, h: int,
        title: str, value: str, subtitle: str,
    ) -> None:
        """通用卡片: 细线边框 + 标题 + 大号数值; 副标题贴底留缝"""
        draw.rectangle([(x, y), (x + w, y + h)], outline=0)
        draw.text((x + 10, y + 8), title, fill=0, font=self.font_small)
        draw.text((x + 10, y + 32), value, fill=0, font=self.font_large)
        if subtitle:
            # 贴底绘制, 与大号温度/金额拉开间距 (避免叠在 46px 字脚下)
            draw.text((x + 10, y + h - 28), subtitle, fill=0, font=self.font_small)

    def _draw_context_bar(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, state: dict
    ) -> None:
        """上下文窗口进度条 + 会话信息 (SHOW_CC_CONTEXT 控制是否绘制)"""
        pct = min(int(state.get("cc_context_percent") or 0), 100)
        bar_w = w - 20
        filled = int(bar_w * pct / 100)

        draw.rectangle([(x, y), (x + w, y + CONTEXT_H)], outline=0)
        draw.text(
            (x + 8, y + 3),
            f"上下文窗口  {pct}%",
            fill=0,
            font=self.font_small,
        )

        bar_y = y + 22
        draw.rectangle([(x + 8, bar_y), (x + 8 + bar_w, bar_y + 14)], outline=0)
        if filled > 0:
            draw.rectangle(
                [(x + 9, bar_y + 1), (x + 8 + filled, bar_y + 13)], fill=0
            )

        session_start = state.get("cc_session_start")
        if session_start:
            elapsed = int(time.time() - session_start)
            mins = elapsed // 60
            rnd = state.get("cc_round", 0)
            info = f"会话: {mins}min  第{rnd}轮"
            draw.text((x + w - 220, y + 3), info, fill=0, font=self.font_small)

    def _draw_session_line(
        self, draw: ImageDraw.Draw, x: int, y: int, state: dict
    ) -> None:
        """活跃面板: Claude 会话费用行 ($ 与 DeepSeek ¥ 分开)"""
        cost = float(state.get("cc_session_cost_usd") or 0)
        model = state.get("cc_model") or ""
        peak = int(state.get("cc_context_peak") or 0)
        parts = [f"本会话 Claude  $ {cost:.2f}"]
        if peak:
            parts.append(f"峰值 {peak}%")
        if model:
            parts.append(model)
        draw.text((x, y), "  ".join(parts), fill=0, font=self.font_small)

    def _draw_model_usage(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        w: int,
        state: dict,
        max_models: int = 2,
        row_h: int = 28,
    ) -> None:
        """模型用量条形图"""
        draw.text((x, y - 2), "模型用量 (DeepSeek)", fill=0, font=self.font_small)
        models = state.get("usage", {}).get("models", [])
        if not models:
            draw.text((x, y + 22), "(暂无数据)", fill=0, font=self.font_small)
            return

        max_tokens = max(m["tokens"] for m in models) if models else 1
        bar_w = w - 260

        for i, model in enumerate(models[:max_models]):
            by = y + 22 + i * row_h
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
            draw.text(
                (x + 160 + bar_w + 6, by + 1),
                info,
                fill=0,
                font=self.font_small,
            )

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
        draw.text((x + 160, y), f"延迟: {latency}ms", fill=0, font=self.font_small)

        svc = state.get("services", {})
        parts = []
        for svc_name in ["deepseek_api", "deepseek_platform"]:
            sv = str(svc.get(svc_name, "unknown"))
            if sv == "up":
                icon = "OK"
            elif sv == "login_expired":
                icon = "LOGIN!"
            elif "error" in sv or "timeout" in sv or sv.startswith("http_"):
                icon = "ERR"
            else:
                icon = "--"
            parts.append(f"{svc_name}: {icon}")
        draw.text((x, y + 20), " | ".join(parts), fill=0, font=self.font_small)

    # ─── 格式化辅助 ────────────────────────────

    @staticmethod
    def _fmt_ago(age: float) -> str:
        """秒差 → "Xs前" / "Xmin前" (同底栏更新时间的口径)"""
        age = max(0, int(age))
        return f"{age}s前" if age < 120 else f"{age // 60}min前"

    @staticmethod
    def _truncate_to_fit(text: str, font, max_w: int) -> str:
        """按像素宽截断加省略号, 防长 slug 溢出卡片"""
        if font.getlength(text) <= max_w:
            return text
        out = text
        while out and font.getlength(out + "…") > max_w:
            out = out[:-1]
        return out + "…"

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.0f}M"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)

    @staticmethod
    def _fmt_duration(sec: int) -> str:
        sec = max(0, int(sec))
        if sec < 60:
            return f"{sec}s"
        mins = sec // 60
        if mins < 60:
            return f"{mins}min"
        return f"{mins // 60}h{mins % 60:02d}m"

    def _balance_subtitle(self, state: dict) -> str:
        bal = state.get("balance", {})
        if not bal.get("is_available", True):
            return "[!] 余额不足, API 不可用"
        try:
            total = float(bal.get("total", 0))
        except (ValueError, TypeError):
            return "预警已开启"
        if total < BALANCE_CRITICAL_THRESHOLD:
            return "[!] 余额严重不足"
        if total < BALANCE_WARN_THRESHOLD:
            return "[!] 余额偏低"
        return "预警已开启"


# ─── 快照 CLI (无硬件, 纯绘制) ────────────────


def _demo_state() -> dict:
    """快照 CLI 缺省演示 state (balance/usage/weather 同 app 初始值样式)"""
    now = time.time()
    return {
        "balance": {"total": "16.58", "currency": "CNY", "is_available": True},
        "usage": {
            "period_spending": "3.42",
            "total_spending": "127.80",
            "total_requests": 1547,
            "total_tokens": 2450000,
            "models": [
                {"name": "deepseek-chat", "tokens": 1500000, "requests": 1200},
                {"name": "deepseek-reasoner", "tokens": 950000, "requests": 347},
            ],
        },
        "weather": {
            "city": "南京", "temp_c": 28, "desc": "多云",
            "feels_c": 30, "humidity": 65, "wind_kmph": 12,
        },
        "cc_status": "idle",
        "last_updated": {
            "balance": now - 300, "usage": now - 300,
            "status": 0, "weather": now - 1200,
        },
        "network_latency_ms": 23,
        "services": {"deepseek_api": "up", "deepseek_platform": "up"},
        "orchestra": {
            "broker_health": "ok",
            "queue_len": 2,
            "active_tasks": 1,
            "last_task": "T-20260819-demo",
            "last_sync": now - 180,
        },
        "orchestra_last_report": {"broker": now - 5, "sync": now - 180},
    }


def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="墨水屏渲染快照 (无硬件, 纯 PIL 绘制)")
    ap.add_argument(
        "--snapshot", metavar="OUT.png", help="输出快照 PNG 路径 (必选)"
    )
    ap.add_argument(
        "--panel", choices=("idle", "active", "orchestra"), default=None,
        help="指定面板; 缺省按 state 解析",
    )
    ap.add_argument(
        "--state", metavar="STATE.json",
        help="状态 JSON 文件; 缺省用内置演示 state",
    )
    args = ap.parse_args()

    if not args.snapshot:
        ap.print_help()
        return 1

    if args.state:
        with open(args.state, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = _demo_state()

    dash = EinkDashboard()  # 不 init_hardware → epd=None, 纯绘制
    panel = args.panel or dash._resolve_display_panel(state)
    img = dash._draw(state, panel)
    img.save(args.snapshot)
    print(
        f"[eink] snapshot saved: {args.snapshot} "
        f"(panel={panel}, {img.size[0]}x{img.size[1]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
