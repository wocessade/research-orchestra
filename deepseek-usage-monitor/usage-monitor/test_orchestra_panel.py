"""e-ink orchestra 面板单元测试 (subsystem-4 Task 2)。

- 纯函数测试: EinkDashboard._resolve_display_panel —— 基面板 idle 且开启
  orchestra 时按时间桶 (ORCHESTRA_ROTATE_SEC) 轮换; now 注入保证确定性。
  SHOW_ORCHESTRA / ORCHESTRA_ROTATE_SEC 是 eink_dashboard 模块级导入常量,
  须 patch eink_dashboard.<名> 而非 config.<名>。
- 快照 CLI 测试: subprocess 跑 `eink_dashboard.py --snapshot`, 不 init_hardware
  (epd=None), 纯 PIL 绘制, 断言输出 800×480。
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

from eink_dashboard import (
    EinkDashboard,
    SHOW_ORCHESTRA,
    ORCHESTRA_ROTATE_SEC,
)

# 固定 60s 轮换周期, 桶号 = int(now // 60):
#   now=100/119 → 桶1 (奇) → orchestra; now=120 → 桶2 (偶) → idle
ROTATE = 60


def orch_state(report: bool = True, **overrides):
    """idle 基面板 + orchestra 数据 (broker 已有上报)"""
    state = {
        "cc_status": "idle",
        "orchestra": {
            "broker_health": "ok",
            "queue_len": 2,
            "active_tasks": 1,
            "last_task": "T-20260819-demo",
            "last_sync": 800.0,
        },
        "orchestra_last_report": (
            {"broker": 1000.0, "sync": 800.0} if report
            else {"broker": 0, "sync": 0}
        ),
    }
    state.update(overrides)
    return state


class ResolveDisplayPanelTest(unittest.TestCase):
    """_resolve_display_panel 纯函数"""

    def setUp(self):
        self.p_show = mock.patch("eink_dashboard.SHOW_ORCHESTRA", True)
        self.p_rot = mock.patch("eink_dashboard.ORCHESTRA_ROTATE_SEC", ROTATE)
        self.p_show.start()
        self.p_rot.start()
        self.addCleanup(self.p_show.stop)
        self.addCleanup(self.p_rot.stop)

    # ─── CC active 时不轮换 (不管时间桶) ──────

    def test_cc_running_always_active(self):
        for now in (100, 120, 179):  # 奇/偶桶
            state = orch_state(cc_status="running")
            self.assertEqual(
                EinkDashboard._resolve_display_panel(state, now), "active"
            )

    def test_cc_panel_active_always_active(self):
        state = orch_state(cc_panel="active")
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 100), "active"
        )
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 120), "active"
        )

    # ─── idle + 开关 + 有上报: 同桶稳定 / 跨桶翻转 ──

    def test_idle_same_bucket_stable(self):
        state = orch_state()
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 100), "orchestra"
        )
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 119), "orchestra"
        )

    def test_idle_cross_bucket_flips(self):
        state = orch_state()
        # 桶1 (奇) → orchestra; 桶2 (偶) → idle; 桶3 (奇) → orchestra
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 100), "orchestra"
        )
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 120), "idle"
        )
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 180), "orchestra"
        )

    def test_cc_panel_idle_rotates_too(self):
        state = orch_state(cc_panel="idle")
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 100), "orchestra"
        )

    def test_now_default_returns_valid_panel(self):
        state = orch_state()
        self.assertIn(
            EinkDashboard._resolve_display_panel(state), ("idle", "orchestra")
        )

    # ─── 无上报不轮换 ────────────────────────

    def test_no_report_no_rotation(self):
        state = orch_state(report=False)
        for now in (100, 120, 180):
            self.assertEqual(
                EinkDashboard._resolve_display_panel(state, now), "idle"
            )

    def test_missing_report_key_no_rotation(self):
        state = {"cc_status": "idle"}  # 无 orchestra 块 (app 初始即有, 防御)
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 100), "idle"
        )

    # ─── 开关关闭不轮换 ──────────────────────

    def test_show_orchestra_false_no_rotation(self):
        state = orch_state()
        with mock.patch("eink_dashboard.SHOW_ORCHESTRA", False):
            self.assertEqual(
                EinkDashboard._resolve_display_panel(state, 100), "idle"
            )

    # ─── cc_status=error 基面板行为不变 ───────

    def test_cc_error_base_panel_unchanged(self):
        """error 的基面板仍是 idle (不翻成 active), 轮换规则与 idle 一致"""
        state = orch_state(cc_status="error")
        self.assertEqual(EinkDashboard._resolve_panel(state), "idle")
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 120), "idle"
        )
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state, 100), "orchestra"
        )

    # ─── hash 集成: orchestra 进展示 hash, 不进数据 hash ──

    def test_display_hash_changes_with_orchestra(self):
        s1 = orch_state()
        s2 = orch_state()
        s2["orchestra"]["queue_len"] = 5
        self.assertNotEqual(
            EinkDashboard._compute_display_hash(s1),
            EinkDashboard._compute_display_hash(s2),
        )

    def test_data_hash_ignores_orchestra(self):
        s1 = orch_state()
        s2 = orch_state()
        s2["orchestra"]["queue_len"] = 5
        self.assertEqual(
            EinkDashboard._compute_data_hash(s1),
            EinkDashboard._compute_data_hash(s2),
        )

    def test_display_hash_panel_uses_display_resolution(self):
        """hash 的 panel 键随桶翻转, 保证切面板时走全刷"""
        state = orch_state()
        with mock.patch("time.time", return_value=100.0):
            h_odd = EinkDashboard._compute_display_hash(state)
        with mock.patch("time.time", return_value=120.0):
            h_even = EinkDashboard._compute_display_hash(state)
        self.assertNotEqual(h_odd, h_even)


class SnapshotCliTest(unittest.TestCase):
    """快照 CLI: eink_dashboard.py --snapshot (无硬件)"""

    SCRIPT = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "eink_dashboard.py"
    )

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    def assert_png_800x480(self, path):
        self.assertTrue(os.path.exists(path), "snapshot file missing")
        with Image.open(path) as img:
            self.assertEqual(img.size, (800, 480))

    def test_snapshot_orchestra_panel(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "orch.png")
            r = self.run_cli("--snapshot", out, "--panel", "orchestra")
            self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
            self.assert_png_800x480(out)

    def test_snapshot_default_panel_demo_state(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "default.png")
            r = self.run_cli("--snapshot", out)
            self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
            self.assert_png_800x480(out)

    def test_snapshot_explicit_state_file(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "state.json")
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(orch_state(report=False), f)
            out = os.path.join(td, "custom.png")
            r = self.run_cli(
                "--snapshot", out, "--panel", "idle", "--state", state_path
            )
            self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
            self.assert_png_800x480(out)


if __name__ == "__main__":
    unittest.main()
