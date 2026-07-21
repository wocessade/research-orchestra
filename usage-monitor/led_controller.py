"""GPIO LED 控制器 — 双色 LED 指示 Claude Code 运行状态

状态映射:
  idle    → 绿灯常亮
  running → 黄灯常亮 (红+绿)
  waiting → 黄灯 500ms 闪烁
  error   → 红灯常亮
"""

from gpiozero import LED
from threading import Thread, Event


class LEDController:
    """控制两颗 GPIO LED (红+绿 = 黄)"""

    def __init__(self, red_pin: int = 17, green_pin: int = 27):
        self.red = LED(red_pin)
        self.green = LED(green_pin)
        self._blink_thread: Thread | None = None
        self._stop_blink = Event()
        self._current_status = "idle"

    # ─── 公共接口 ──────────────────────────────

    def set_status(self, status: str) -> None:
        """设置状态: idle | running | waiting | error

        compact-warning 等非 LED 相关状态会被忽略，
        LED 保持当前状态不变。
        """
        # 只处理与 LED 相关的四种状态
        if status not in ("idle", "running", "waiting", "error"):
            return

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

    def cleanup(self) -> None:
        """程序退出时清理 GPIO 资源"""
        self._stop_blinking()
        self._all_off()
        self.red.close()
        self.green.close()

    # ─── 内部实现 ──────────────────────────────

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
