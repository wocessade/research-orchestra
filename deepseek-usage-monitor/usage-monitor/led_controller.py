"""GPIO LED 控制器 — 双色 LED 指示 Claude Code 运行状态

状态映射:
  idle    → 绿灯常亮
  running → 黄灯常亮 (红+绿)
  waiting → 黄灯 500ms 闪烁
  error   → 红灯常亮
"""

import os
from threading import Thread, Event, Lock

from waveshare_epd import h616_gpio


class LEDController:
    """控制两颗 GPIO LED (红+绿 = 黄)

    引脚可用环境变量 LED_RED_PIN / LED_GREEN_PIN 覆盖
    (WalnutPi 1B: 红=PI0=256, 绿=PI1=257)
    """

    def __init__(self, red_pin: int = 5, green_pin: int = 6):
        red_pin = int(os.getenv("LED_RED_PIN", red_pin))
        green_pin = int(os.getenv("LED_GREEN_PIN", green_pin))
        self._red = red_pin
        self._green = green_pin
        h616_gpio.open_output(red_pin)
        h616_gpio.open_output(green_pin)
        self._blink_thread: Thread | None = None
        self._stop_blink = Event()
        self._current_status = "idle"
        self._lock = Lock()

    # ─── 公共接口 ──────────────────────────────

    def set_status(self, status: str) -> None:
        """设置状态: idle | running | waiting | error

        compact-warning 等非 LED 相关状态会被忽略，
        LED 保持当前状态不变。
        """
        if status not in ("idle", "running", "waiting", "error"):
            return

        join_thread: Thread | None = None
        with self._lock:
            if status == self._current_status:
                return

            self._current_status = status
            join_thread = self._detach_blink_thread()
            self._all_off()

            if status == "idle":
                self._set(self._green, 1)
            elif status == "running":
                self._set(self._red, 1)
                self._set(self._green, 1)  # red + green = yellow
            elif status == "waiting":
                self._start_blinking()
            elif status == "error":
                self._set(self._red, 1)

        # join 必须在锁外, 避免与 blink 线程死锁
        if join_thread is not None:
            join_thread.join(timeout=1)

    def cleanup(self) -> None:
        """程序退出时清理 GPIO 资源"""
        join_thread: Thread | None = None
        with self._lock:
            join_thread = self._detach_blink_thread()
            self._all_off()
        if join_thread is not None:
            join_thread.join(timeout=1)
        h616_gpio.release(self._red)
        h616_gpio.release(self._green)

    # ─── 内部实现 ──────────────────────────────

    def _set(self, pin: int, value: int) -> None:
        h616_gpio.write(pin, value)

    def _detach_blink_thread(self) -> Thread | None:
        """发停止信号并摘下线程引用 (调用方须已持锁; join 在锁外)。"""
        thread = self._blink_thread
        self._blink_thread = None
        if thread and thread.is_alive():
            self._stop_blink.set()
            return thread
        return None

    def _start_blinking(self) -> None:
        self._stop_blink.clear()
        self._blink_thread = Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    def _blink_loop(self) -> None:
        while not self._stop_blink.is_set():
            with self._lock:
                if self._current_status != "waiting":
                    break
                self._set(self._red, 1)
                self._set(self._green, 1)
            self._stop_blink.wait(0.5)
            with self._lock:
                if self._current_status != "waiting":
                    break
                self._all_off()
            self._stop_blink.wait(0.5)

    def _all_off(self) -> None:
        self._set(self._red, 0)
        self._set(self._green, 0)
