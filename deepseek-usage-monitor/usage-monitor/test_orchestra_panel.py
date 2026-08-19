"""e-ink orchestra 面板单元测试 (subsystem-4 Task 2, D9 融合面板)。

- 纯函数测试: EinkDashboard._resolve_display_panel —— 基面板 idle 且开启
  orchestra 时恒定展示融合 orchestra 面板 (无轮换, 无 now 参数)。
  SHOW_ORCHESTRA 是 eink_dashboard 模块级导入常量,
  须 patch eink_dashboard.SHOW_ORCHESTRA 而非 config.SHOW_ORCHESTRA。
- 辅助函数测试: _fmt_age (epoch / ISO → Xs前 / Xmin前 / Xh前)。
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

from eink_dashboard import EinkDashboard


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
            "recent_tasks": [
                {"slug": "T-20260819-e2e-dsh",
                 "status": "running", "ts": 700.0},
                {"slug": "T-20260819-ctl-single",
                 "status": "done", "ts": 400.0},
            ],
        },
        "orchestra_last_report": (
            {"broker": 1000.0, "sync": 800.0} if report
            else {"broker": 0, "sync": 0}
        ),
    }
    state.update(overrides)
    return state


class ResolveDisplayPanelTest(unittest.TestCase):
    """_resolve_display_panel 纯函数 (D9: 无轮换, 恒定决议)"""

    def setUp(self):
        self.p_show = mock.patch("eink_dashboard.SHOW_ORCHESTRA", True)
        self.p_show.start()
        self.addCleanup(self.p_show.stop)

    # ─── CC active 时永远展示 active 面板 ──────

    def test_cc_running_always_active(self):
        state = orch_state(cc_status="running")
        self.assertEqual(EinkDashboard._resolve_display_panel(state), "active")

    def test_cc_panel_active_always_active(self):
        state = orch_state(cc_panel="active")
        self.assertEqual(EinkDashboard._resolve_display_panel(state), "active")

    # ─── idle + SHOW_ORCHESTRA: 恒定融合面板 ────

    def test_idle_with_show_orchestra_fused_constant(self):
        """idle 基面板 → 恒定为 orchestra, 无时间依赖 (随时调用同结果)"""
        state = orch_state()
        for _ in range(3):
            self.assertEqual(
                EinkDashboard._resolve_display_panel(state), "orchestra"
            )

    def test_cc_panel_idle_fused_too(self):
        state = orch_state(cc_panel="idle")
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state), "orchestra"
        )

    # ─── 无上报 / 缺 orchestra 块仍展示融合面板 (D9 行为变更) ──

    def test_no_report_still_orchestra(self):
        """无 broker 上报 (状态条显示 --) 也恒定 orchestra, 不再回退 idle"""
        state = orch_state(report=False)
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state), "orchestra"
        )

    def test_missing_orchestra_block_still_orchestra(self):
        state = {"cc_status": "idle"}  # 防御: 无 orchestra 块
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state), "orchestra"
        )

    # ─── 开关关闭回退旧 idle 面板 ──────────────

    def test_show_orchestra_false_returns_idle(self):
        state = orch_state()
        with mock.patch("eink_dashboard.SHOW_ORCHESTRA", False):
            self.assertEqual(
                EinkDashboard._resolve_display_panel(state), "idle"
            )

    # ─── cc_status=error 基面板行为不变 ───────

    def test_cc_error_base_panel_unchanged(self):
        """error 的基面板仍是 idle (不翻成 active); 展示决议与 idle 一致"""
        state = orch_state(cc_status="error")
        self.assertEqual(EinkDashboard._resolve_panel(state), "idle")
        self.assertEqual(
            EinkDashboard._resolve_display_panel(state), "orchestra"
        )

    # ─── hash 集成: orchestra 内容变化 → data hash 与 display hash 均变 ──

    def test_display_hash_changes_with_orchestra(self):
        s1 = orch_state()
        s2 = orch_state()
        s2["orchestra"]["queue_len"] = 5
        self.assertNotEqual(
            EinkDashboard._compute_display_hash(s1),
            EinkDashboard._compute_display_hash(s2),
        )

    def test_data_hash_changes_with_orchestra(self):
        """D9: 融合面板内容即主数据 → orchestra 变化走全刷"""
        s1 = orch_state()
        s2 = orch_state()
        s2["orchestra"]["recent_tasks"] = [
            {"slug": "T-new", "status": "running", "ts": 500.0}
        ]
        self.assertNotEqual(
            EinkDashboard._compute_data_hash(s1),
            EinkDashboard._compute_data_hash(s2),
        )

    def test_display_hash_panel_uses_display_resolution(self):
        """hash 的 panel 键随 SHOW_ORCHESTRA 决议变化 → 切面板走全刷"""
        state = orch_state()
        with mock.patch("eink_dashboard.SHOW_ORCHESTRA", True):
            h_on = EinkDashboard._compute_display_hash(state)
        with mock.patch("eink_dashboard.SHOW_ORCHESTRA", False):
            h_off = EinkDashboard._compute_display_hash(state)
        self.assertNotEqual(h_on, h_off)


class FmtAgeTest(unittest.TestCase):
    """_fmt_age: epoch / ISO → Xs前 / Xmin前 / Xh前"""

    def test_epoch_seconds(self):
        with mock.patch("time.time", return_value=1000.0):
            self.assertEqual(EinkDashboard._fmt_age(999.9), "0s前")
            self.assertEqual(EinkDashboard._fmt_age(995.0), "5s前")
            self.assertEqual(EinkDashboard._fmt_age(940.0), "1min前")
            self.assertEqual(EinkDashboard._fmt_age(100.0), "15min前")
            self.assertEqual(EinkDashboard._fmt_age(-6200.0), "2h前")

    def test_iso_string(self):
        from datetime import datetime, timezone

        now_ts = 1_800_000_000.0
        # 从 epoch 生成 ISO 串, 免手算 (2027-01-15T08:00:00Z ≈ 1800000000)
        iso_now = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
        iso_now_z = iso_now.replace("+00:00", "Z")
        iso_minus_15 = datetime.fromtimestamp(
            now_ts - 900, tz=timezone.utc
        ).isoformat()
        with mock.patch("time.time", return_value=now_ts):
            self.assertEqual(EinkDashboard._fmt_age(iso_now), "0s前")
            self.assertEqual(EinkDashboard._fmt_age(iso_now_z), "0s前")
            self.assertEqual(EinkDashboard._fmt_age(iso_minus_15), "15min前")

    def test_invalid_returns_dash(self):
        with mock.patch("time.time", return_value=1000.0):
            self.assertEqual(EinkDashboard._fmt_age(None), "--")
            self.assertEqual(EinkDashboard._fmt_age("garbage"), "--")
            self.assertEqual(EinkDashboard._fmt_age(""), "--")
            self.assertEqual(EinkDashboard._fmt_age("not-a-date"), "--")


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
