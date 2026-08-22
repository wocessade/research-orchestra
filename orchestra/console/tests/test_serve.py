import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from feed_serve import make_server


class ServeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.console = Path(self.tmp.name) / "console"
        self.out = self.console / "out"
        self.out.mkdir(parents=True)
        (self.console / "messages.md").write_text(
            "## 2026-08-21 08:00 — 早上好\n第一条\n", encoding="utf-8")
        (self.console / "console-schedule.toml").write_text(
            '[system]\nradar = "23:30"\n[[personal]]\n'
            'date = "2026-09-01"\ntime = "09:00"\ntitle = "开学报到"\n',
            encoding="utf-8")
        self.server = make_server(self.out, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def _json(self, method, path, payload=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp.status, json.loads(raw.decode("utf-8"))

    def test_static_file(self):
        (self.out / "hello.txt").write_text("hi", encoding="utf-8")
        status, body = self._get("/hello.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"hi")

    def test_messages_hot_regen(self):
        status, body = self._get("/messages.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["latest"][0]["title"], "早上好")
        time.sleep(0.05)
        (self.console / "messages.md").write_text(
            "## 2026-08-21 09:00 — 新留言\n第二条\n", encoding="utf-8")
        status, body = self._get("/messages.json")
        self.assertEqual(json.loads(body)["latest"][0]["title"], "新留言")

    def test_messages_degraded_on_bad_md(self):
        time.sleep(0.05)
        (self.console / "messages.md").write_text(
            "## 不是时间 — 空标题\nbody\n## 2026-08-21 09:00 —\nbody",
            encoding="utf-8")
        status, body = self._get("/messages.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"latest": [], "pending": [], "alerts": []})

    def test_messages_degraded_parsed_once(self):
        # 坏文件也必须走 mtime 缓存：mtime 未变不重解析
        import feed_messages

        real_parse = feed_messages.parse_messages
        calls = 0

        def counting_parse(text):
            nonlocal calls
            calls += 1
            return real_parse(text)

        time.sleep(0.05)
        (self.console / "messages.md").write_text(
            "## 不是时间 — 空标题\nbody\n## 2026-08-21 09:00 —\nbody",
            encoding="utf-8")
        with mock.patch.object(feed_messages, "parse_messages", side_effect=counting_parse):
            for _ in range(3):
                status, body = self._get("/messages.json")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body),
                                 {"latest": [], "pending": [], "alerts": []})
            self.assertEqual(calls, 1)

    def test_messages_missing_md_degrades(self):
        (self.console / "messages.md").unlink()
        status, body = self._get("/messages.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"latest": [], "pending": [], "alerts": []})

    def test_messages_parsed_once_per_mtime(self):
        import feed_messages

        real_parse = feed_messages.parse_messages
        calls = 0

        def counting_parse(text):
            nonlocal calls
            calls += 1
            return real_parse(text)

        with mock.patch.object(feed_messages, "parse_messages", side_effect=counting_parse):
            for _ in range(3):
                status, _ = self._get("/messages.json")
                self.assertEqual(status, 200)
            self.assertEqual(calls, 1)
            time.sleep(0.05)
            (self.console / "messages.md").write_text(
                "## 2026-08-21 09:00 — 新留言\n第二条\n", encoding="utf-8")
            status, _ = self._get("/messages.json")
            self.assertEqual(status, 200)
            self.assertEqual(calls, 2)

    def test_two_servers_isolated(self):
        tmp2 = tempfile.TemporaryDirectory()
        try:
            console2 = Path(tmp2.name) / "console"
            out2 = console2 / "out"
            out2.mkdir(parents=True)
            (console2 / "messages.md").write_text(
                "## 2026-08-21 10:00 — 第二台\n内容二\n", encoding="utf-8")
            server2 = make_server(out2, "127.0.0.1", 0)
            thread2 = threading.Thread(target=server2.serve_forever, daemon=True)
            thread2.start()
            try:
                def get_from(server, path):
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                    conn.request("GET", path)
                    response = conn.getresponse()
                    body = response.read()
                    conn.close()
                    return response.status, body

                status, body = get_from(self.server, "/messages.json")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["latest"][0]["title"], "早上好")
                status, body = get_from(server2, "/messages.json")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["latest"][0]["title"], "第二台")
                time.sleep(0.05)
                (console2 / "messages.md").write_text(
                    "## 2026-08-21 11:00 — 第二台更新\n内容更新\n", encoding="utf-8")
                status, body = get_from(server2, "/messages.json")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["latest"][0]["title"], "第二台更新")
                status, body = get_from(self.server, "/messages.json")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["latest"][0]["title"], "早上好")
            finally:
                server2.shutdown()
                server2.server_close()
        finally:
            tmp2.cleanup()

    def test_radar_api_lookup(self):
        results = self.console.parent / "results"
        d = results / "T-20260819-nightly-radar" / "attempt-1"
        d.mkdir(parents=True)
        (d / "state.json").write_text(
            json.dumps({"slug": "T-x", "status": "done", "started_at": "t"}),
            encoding="utf-8")
        (d / "digest.txt").write_text("文献日报 lookup\n", encoding="utf-8")
        (d / "top5.json").write_text("[]", encoding="utf-8")
        self.server.results_root = results
        status, data = self._json("GET", "/api/radar?date=2026-08-19")
        self.assertEqual(status, 200)
        self.assertTrue(data["available"])
        self.assertIn("lookup", data["digest_txt"])
        self.assertTrue(any(h.get("date") == "2026-08-19" for h in data.get("history") or []))

    def test_unknown_404(self):
        status, _ = self._get("/nope.json")
        self.assertEqual(status, 404)

    def test_personal_crud_http(self):
        status, data = self._json("GET", "/api/personal")
        self.assertEqual(status, 200)
        self.assertEqual(data["personal"][0]["title"], "开学报到")
        status, data = self._json("POST", "/api/personal", {
            "date": "2026-09-03", "time": "10:00", "title": "组会",
        })
        self.assertEqual(status, 200)
        self.assertEqual(len(data["personal"]), 2)
        toml = (self.console / "console-schedule.toml").read_text(encoding="utf-8")
        self.assertIn("组会", toml)
        self.assertIn('radar = "23:30"', toml)
        ics = (self.out / "personal.ics").read_text(encoding="utf-8")
        self.assertIn("组会", ics)
        new_id = [p["id"] for p in data["personal"] if p["title"] == "组会"][0]
        status, data = self._json("PUT", "/api/personal", {
            "id": new_id, "date": "2026-09-03", "time": "11:00", "title": "组会改期",
        })
        self.assertEqual(status, 200)
        self.assertTrue(any(p["title"] == "组会改期" for p in data["personal"]))
        rid = [p["id"] for p in data["personal"] if p["title"] == "组会改期"][0]
        status, data = self._json("DELETE", f"/api/personal?id={rid}")
        self.assertEqual(status, 200)
        self.assertEqual([p["title"] for p in data["personal"]], ["开学报到"])
        status, data = self._json("DELETE", "/api/personal?id=missing")
        self.assertEqual(status, 404)
        status, data = self._json("POST", "/api/personal", {
            "date": "2026-09-03", "time": "99:00", "title": "坏",
        })
        self.assertEqual(status, 400)

    def test_personal_post_updates_status_upcoming(self):
        from datetime import date, timedelta
        (self.out / "status.json").write_text(
            json.dumps({"upcoming_personal": []}), encoding="utf-8")
        soon = date.today() + timedelta(days=2)
        status, _ = self._json("POST", "/api/personal", {
            "date": soon.isoformat(), "time": "14:00", "title": "临近测",
        })
        self.assertEqual(status, 200)
        st = json.loads((self.out / "status.json").read_text(encoding="utf-8"))
        titles = [u["title"] for u in st["upcoming_personal"]]
        self.assertIn("临近测", titles)

    def test_personal_post_does_not_touch_system(self):
        self._json("POST", "/api/personal", {
            "date": "2026-09-08", "time": "08:00", "title": "实验",
        })
        after = (self.console / "console-schedule.toml").read_text(encoding="utf-8")
        self.assertIn('radar = "23:30"', after)
        self.assertIn("实验", after)

    def test_personal_done_toggle(self):
        status, data = self._json("GET", "/api/personal")
        ident = data["personal"][0]["id"]
        status, data = self._json("POST", "/api/personal/done", {"id": ident})
        self.assertEqual(status, 200)
        self.assertTrue(data["personal"][0]["done"])
        toml = (self.console / "console-schedule.toml").read_text(encoding="utf-8")
        self.assertIn("done = true", toml)

    def test_messages_merge_status_without_md_change(self):
        (self.out / "status.json").write_text(
            json.dumps({"4b": "离线", "walnut": "在线"}), encoding="utf-8")
        status, body = self._get("/messages.json")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["latest"][0]["title"], "早上好")
        self.assertTrue(any(a["title"] == "4B 离线" for a in data["alerts"]))

    def test_pending_api_roundtrip(self):
        status, data = self._json("POST", "/api/pending", {"text": "拍板预算"})
        self.assertEqual(status, 200)
        self.assertEqual([p["text"] for p in data["pending"]], ["拍板预算"])
        self.assertTrue(data["pending"][0]["dismissable"])
        md = (self.console / "messages.md").read_text(encoding="utf-8")
        self.assertIn("- 待决：拍板预算", md)
        status, body = self._get("/messages.json")
        self.assertIn("拍板预算", json.loads(body)["pending"][0]["text"])
        encoded = "/api/pending?text=" + quote("拍板预算")
        status, data = self._json("DELETE", encoded)
        self.assertEqual(status, 200)
        self.assertEqual(data["pending"], [])
        status, data = self._json("DELETE", encoded)
        self.assertEqual(status, 404)
        status, data = self._json("POST", "/api/pending", {"text": "   "})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
