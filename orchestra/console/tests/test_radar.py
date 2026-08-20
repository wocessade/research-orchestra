import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from feed_radar import (
    build_digest_html,
    find_radar,
    scan_attempts,
    scan_experiments,
)

PAPERS = [{"arxiv_id": "2608.16798", "title": "ClawGym II", "total": 76},
          {"arxiv_id": "2608.10001", "title": "Paper B", "total": 60}]


def _write(path: Path, name: str, value) -> None:
    p = path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    else:
        p.write_text(value, encoding="utf-8")


def _state(status, started="2026-08-19T23:31:00+00:00"):
    return {"slug": "T-x", "executor": "dsh", "attempt": 1, "status": status,
            "error": None, "started_at": started, "elapsed_s": 1.0}


def make_four_stage(root: Path) -> None:
    for slug in ("10-fetch", "20-rank", "30-render", "40-notify"):
        d = root / f"T-20260819-{slug}" / "attempt-1"
        _write(d, "state.json", _state("done"))
    rd = root / "T-20260819-30-render" / "attempt-1"
    _write(rd, "digest.json", PAPERS)
    _write(rd, "top5.json", [{"arxiv_id": "2608.16798", "title": "ClawGym II",
                              "total": 76, "selection_reason": "overall"}])
    _write(rd, "validation.json", {"date": "2026-08-19", "status": "passed"})
    _write(rd, "digest.txt", "文献日报 2026-08-19\n\n1. ClawGym II\n")


def make_legacy(root: Path) -> None:
    d = root / "T-20260819-nightly-radar"
    _write(d / "attempt-1", "state.json", _state("failed"))
    _write(d / "attempt-1", "digest.txt", "旧的失败产物")
    _write(d / "attempt-2", "state.json", _state("done"))
    _write(d / "attempt-2", "digest.json", PAPERS)
    _write(d / "attempt-2", "top5.json", [[76, "2608.16798",
            {"topic": 31, "method": 15, "source": 9, "network": 6,
             "applied": 8, "archival": 7}]])
    _write(d / "attempt-2", "digest.txt", "文献日报 2026-08-19\n")


class FindRadarTest(unittest.TestCase):
    def test_empty_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_radar(Path(tmp)), {"available": False})

    def test_four_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_four_stage(Path(tmp))
            radar = find_radar(Path(tmp))
            self.assertTrue(radar["available"])
            self.assertEqual(radar["mode"], "four-stage")
            self.assertEqual(radar["date"], "2026-08-19")
            self.assertEqual([s["name"] for s in radar["stages"]],
                             ["fetch", "rank", "render", "notify"])
            self.assertTrue(all(s["status"] == "done" for s in radar["stages"]))
            self.assertEqual(radar["top5"][0]["title"], "ClawGym II")

    def test_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_legacy(Path(tmp))
            radar = find_radar(Path(tmp))
            self.assertTrue(radar["available"])
            self.assertEqual(radar["mode"], "legacy")
            self.assertEqual([s["name"] for s in radar["stages"]],
                             ["attempt-1", "attempt-2"])
            self.assertEqual(radar["stages"][1]["status"], "done")

    def test_artifact_from_done_attempt(self):
        # attempt-1 failed 也有 digest.txt，产物必须来自 done 的 attempt-2
        with tempfile.TemporaryDirectory() as tmp:
            make_legacy(Path(tmp))
            radar = find_radar(Path(tmp))
            self.assertIn("文献日报", radar["digest_txt"])

    def test_legacy_top5_triple_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_legacy(Path(tmp))
            radar = find_radar(Path(tmp))
            self.assertEqual(radar["top5"][0]["id"], "2608.16798")
            self.assertEqual(radar["top5"][0]["title"], "ClawGym II")  # 从 digest.json 补标题

    def test_missing_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "T-20260819-10-fetch" / "attempt-1", "state.json", _state("done"))
            _write(root / "T-20260819-30-render" / "attempt-1", "state.json", _state("done"))
            _write(root / "T-20260819-30-render" / "attempt-1", "digest.json", [])
            radar = find_radar(root)
            self.assertEqual(radar["stages"][1]["status"], "missing")


class BuildDigestHtmlTest(unittest.TestCase):
    def test_escaping(self):
        html = build_digest_html({"available": True, "date": "2026-08-19",
                                  "mode": "legacy", "validation": {"status": "passed"},
                                  "digest_txt": "<script>alert(1)</script>"})
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert", html)


class ScanAttemptsTest(unittest.TestCase):
    def test_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "T-a" / "attempt-2", "state.json", _state("done"))
            _write(root / "T-b" / "attempt-1", "state.json", _state("failed", "x"))
            rows = scan_attempts(root)
            self.assertEqual(len(rows), 2)
            by_task = {r["task"]: r for r in rows}
            self.assertEqual(by_task["T-a"]["attempt"], 2)
            self.assertEqual(by_task["T-a"]["status"], "done")

    def test_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(5):
                _write(root / f"T-{i}" / "attempt-1", "state.json", _state("done"))
            self.assertEqual(len(scan_attempts(root, limit=3)), 3)


class ScanExperimentsTest(unittest.TestCase):
    def test_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(scan_experiments(Path(tmp)),
                             {"available": False, "cards": []})

    def test_cards_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "experiments" / "EXP-001" / "card.md"
            card.parent.mkdir(parents=True)
            card.write_text("---\nid: EXP-001\nstatus: designed\n"
                            "created: 2026-08-19\n---\n\n# 标题\n", encoding="utf-8")
            res = scan_experiments(root)
            self.assertTrue(res["available"])
            self.assertEqual(res["cards"][0]["id"], "EXP-001")
            self.assertEqual(res["cards"][0]["status"], "designed")


if __name__ == "__main__":
    unittest.main()
