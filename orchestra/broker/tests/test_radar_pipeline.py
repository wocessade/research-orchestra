"""雷达语义校验、确定性选择和持久通知测试。"""
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

import artifact_validators
import radar_notify
import radar_render


def paper(index, total_parts, novelty, abstract, confidence=0.8):
    topic, method, applied, archival = total_parts
    return {
        "title": f"Paper {index}",
        "arxiv_id": f"2608.{index:05d}",
        "url": f"https://arxiv.org/abs/2608.{index:05d}",
        "categories": ["cs.CL"],
        "abstract": abstract,
        "scores": {
            "topic": topic,
            "method": method,
            "applied": applied,
            "archival": archival,
            "novelty": novelty,
        },
        "total": topic + method + applied + archival,
        "quality_signals": {
            "peer_reviewed": "unknown",
            "code_available": "unknown",
            "dataset_available": "unknown",
        },
        "evidence": ["abstract evidence"],
        "counter_evidence": [],
        "unknowns": ["full text unavailable"],
        "confidence": confidence,
        "rationale": f"Paper {index} has a distinct contribution.",
    }


class RadarPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fetch_root = self.root / "T-20260820-nightly-radar-10-fetch"
        self.fetch_attempt = self.fetch_root / "attempt-1"
        self.fetch_attempt.mkdir(parents=True)
        self.rank_root = self.root / "T-20260820-nightly-radar-20-rank"
        self.rank_attempt = self.rank_root / "attempt-1"
        self.rank_attempt.mkdir(parents=True)
        self.papers = [
            paper(1, (38, 24, 18, 14), 4, "agent language model benchmark reasoning"),
            paper(2, (37, 23, 18, 14), 5, "multimodal agent benchmark planning"),
            paper(3, (36, 22, 18, 14), 6, "language model tool agent evaluation"),
            paper(4, (28, 18, 12, 10), 10, "novel agent memory architecture"),
            paper(5, (20, 15, 10, 8), 3, "quantum chemistry molecular catalyst spectroscopy"),
            paper(6, (22, 15, 10, 8), 2, "agent language model benchmark tools"),
        ]
        fetch_papers = [
            {
                "title": item["title"],
                "arxiv_id": item["arxiv_id"],
                "url": item["url"],
                "submitted_at": "2026-08-20T00:00:00Z",
                "abstract": item["abstract"],
                "categories": item["categories"],
                "authors": ["Researcher"],
            }
            for item in self.papers
        ]
        fetch_raw = json.dumps(fetch_papers).encode("utf-8")
        (self.fetch_attempt / "papers_all.json").write_bytes(fetch_raw)
        (self.fetch_attempt / "fetch_summary.json").write_text(
            json.dumps({
                "deduplicated_count": len(fetch_papers),
                "source_counts": {"cs.CL": len(fetch_papers), "cs.LG": 0},
            }),
            encoding="utf-8",
        )
        (self.fetch_attempt / "state.json").write_text(
            json.dumps({"status": "done"}), encoding="utf-8"
        )
        (self.rank_attempt / "scored_papers.json").write_text(
            json.dumps(self.papers), encoding="utf-8"
        )
        (self.rank_attempt / "ranking_summary.json").write_text(
            json.dumps({
                "candidate_count": 6,
                "eligible_count": 6,
                "input_count": 6,
                "input_sha256": hashlib.sha256(fetch_raw).hexdigest(),
            }),
            encoding="utf-8",
        )
        (self.rank_attempt / "state.json").write_text(
            json.dumps({"status": "done"}), encoding="utf-8"
        )

    def test_rank_validator_rejects_total_mismatch(self):
        self.assertEqual(artifact_validators.validate_rank(self.rank_attempt), [])
        self.papers[0]["total"] += 1
        (self.rank_attempt / "scored_papers.json").write_text(
            json.dumps(self.papers), encoding="utf-8"
        )
        errors = artifact_validators.validate_rank(self.rank_attempt)
        self.assertTrue(any("score sum" in error for error in errors))

    def test_rank_validator_rejects_upstream_id_set_and_count_mismatch(self):
        self.papers.pop()
        self.papers[0]["arxiv_id"] = "2608.99999"
        (self.rank_attempt / "scored_papers.json").write_text(
            json.dumps(self.papers), encoding="utf-8"
        )
        summary = json.loads(
            (self.rank_attempt / "ranking_summary.json").read_text(encoding="utf-8")
        )
        summary["candidate_count"] = len(self.papers)
        summary["eligible_count"] = len(self.papers)
        (self.rank_attempt / "ranking_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )

        errors = artifact_validators.validate_rank(self.rank_attempt)

        self.assertTrue(any("count does not match upstream" in error for error in errors))
        self.assertTrue(any("arxiv_id set does not match" in error for error in errors))

    def test_rank_validator_rejects_broken_upstream_sha_closure(self):
        summary_path = self.rank_attempt / "ranking_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["input_sha256"] = "0" * 64
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        errors = artifact_validators.validate_rank(self.rank_attempt)

        self.assertTrue(any("input_sha256 mismatch" in error for error in errors))

    def test_rank_validator_rejects_swapped_upstream_fields_by_arxiv_id(self):
        self.papers[0]["title"], self.papers[1]["title"] = (
            self.papers[1]["title"],
            self.papers[0]["title"],
        )
        self.papers[2]["categories"], self.papers[3]["categories"] = (
            self.papers[3]["categories"],
            self.papers[2]["categories"],
        )
        (self.rank_attempt / "scored_papers.json").write_text(
            json.dumps(self.papers), encoding="utf-8"
        )

        errors = artifact_validators.validate_rank(self.rank_attempt)

        self.assertTrue(any("[0].title" in error for error in errors))
        self.assertTrue(any("[1].title" in error for error in errors))

    def test_rank_validator_rejects_forged_upstream_fields(self):
        self.papers[0]["url"] = "https://example.invalid/forged"
        self.papers[1]["abstract"] = "forged abstract"
        self.papers[2]["categories"] = ["cs.LG"]
        (self.rank_attempt / "scored_papers.json").write_text(
            json.dumps(self.papers), encoding="utf-8"
        )

        errors = artifact_validators.validate_rank(self.rank_attempt)

        self.assertTrue(any("[0].url" in error for error in errors))
        self.assertTrue(any("[1].abstract" in error for error in errors))
        self.assertTrue(any("[2].categories" in error for error in errors))

    def test_render_is_deterministic_and_records_trace(self):
        out1 = self.root / "render-1"
        out2 = self.root / "render-2"
        first = radar_render.render(self.rank_root, out1, "20260820")
        second = radar_render.render(self.rank_root, out2, "20260820")
        top1 = json.loads((out1 / "top5.json").read_text(encoding="utf-8"))
        top2 = json.loads((out2 / "top5.json").read_text(encoding="utf-8"))
        self.assertEqual(top1, top2)
        self.assertEqual(
            [item["selection_reason"] for item in top1],
            ["overall", "overall", "overall", "novelty", "diversity"],
        )
        self.assertEqual(top1[-1]["arxiv_id"], "2608.00005")
        self.assertEqual(first["input_sha256"], second["input_sha256"])
        self.assertEqual(first["algorithm_version"], "radar-render-v1")
        self.assertEqual(artifact_validators.validate_render(out1), [])

    def test_notify_sends_once_and_then_skips(self):
        render_root = self.root / "render-root"
        attempt = render_root / "attempt-1"
        radar_render.render(self.rank_root, attempt, "20260820")
        (attempt / "state.json").write_text(
            json.dumps({"status": "done"}), encoding="utf-8"
        )
        sender = self.root / "sender.py"
        sender.write_text(
            "from pathlib import Path\n"
            "p=Path(__file__).with_name('send-count.txt')\n"
            "p.write_text((p.read_text() if p.exists() else '')+'sent\\n')\n",
            encoding="utf-8",
        )
        state_root = self.root / "notifications"
        first_out = self.root / "notify-1"
        second_out = self.root / "notify-2"
        self.assertEqual(
            radar_notify.notify(render_root, state_root, first_out, "20260820", sender), 0
        )
        self.assertEqual(
            radar_notify.notify(render_root, state_root, second_out, "20260820", sender), 0
        )
        count = (self.root / "send-count.txt").read_text(encoding="utf-8")
        self.assertEqual(count.count("sent"), 1)
        skipped = json.loads((second_out / "notification.json").read_text(encoding="utf-8"))
        self.assertEqual(skipped["status"], "skipped")

    def test_notify_refuses_ambiguous_retry(self):
        render_root = self.root / "render-root-unknown"
        attempt = render_root / "attempt-1"
        radar_render.render(self.rank_root, attempt, "20260820")
        (attempt / "state.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
        state_root = self.root / "notifications-unknown"
        state_root.mkdir()
        (state_root / "radar-20260820.json").write_text(
            json.dumps({"status": "sending"}), encoding="utf-8"
        )
        output = self.root / "notify-unknown"
        rc = radar_notify.notify(
            render_root, state_root, output, "20260820", self.root / "unused.py"
        )
        self.assertEqual(rc, 2)
        result = json.loads((output / "notification.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "unknown")

    def test_notify_retries_after_sender_explicitly_reports_not_sent(self):
        render_root = self.root / "render-root-retry"
        attempt = render_root / "attempt-1"
        radar_render.render(self.rank_root, attempt, "20260820")
        (attempt / "state.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
        sender = self.root / "retry-sender.py"
        sender.write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "p=Path(__file__).with_name('retry-count.txt')\n"
            "n=int(p.read_text())+1 if p.exists() else 1\n"
            "p.write_text(str(n))\n"
            "raise SystemExit(10 if n == 1 else 0)\n",
            encoding="utf-8",
        )
        state_root = self.root / "notifications-retry"
        first_out = self.root / "notify-retry-1"
        second_out = self.root / "notify-retry-2"

        self.assertEqual(
            radar_notify.notify(render_root, state_root, first_out, "20260820", sender), 1
        )
        first = json.loads((first_out / "notification.json").read_text(encoding="utf-8"))
        self.assertEqual(first["status"], "not_sent")
        self.assertEqual(
            radar_notify.notify(render_root, state_root, second_out, "20260820", sender), 0
        )
        second = json.loads((second_out / "notification.json").read_text(encoding="utf-8"))
        self.assertEqual(second["status"], "sent")
        self.assertEqual(
            (self.root / "retry-count.txt").read_text(encoding="utf-8"), "2"
        )

    def test_notify_nonzero_without_explicit_not_sent_is_ambiguous(self):
        render_root = self.root / "render-root-failed"
        attempt = render_root / "attempt-1"
        radar_render.render(self.rank_root, attempt, "20260820")
        (attempt / "state.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
        sender = self.root / "ambiguous-sender.py"
        sender.write_text("raise SystemExit(1)\n", encoding="utf-8")
        state_root = self.root / "notifications-failed"
        output = self.root / "notify-failed"

        self.assertEqual(
            radar_notify.notify(render_root, state_root, output, "20260820", sender), 2
        )
        result = json.loads((output / "notification.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
