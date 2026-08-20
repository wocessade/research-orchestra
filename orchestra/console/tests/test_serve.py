import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from feed_serve import make_server


class ServeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.console = Path(self.tmp.name) / "console"
        self.out = self.console / "out"
        self.out.mkdir(parents=True)
        (self.console / "messages.md").write_text(
            "## 2026-08-21 08:00 — 早上好\n第一条\n", encoding="utf-8")
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

    def test_messages_missing_md_degrades(self):
        (self.console / "messages.md").unlink()
        status, body = self._get("/messages.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"latest": [], "pending": [], "alerts": []})

    def test_unknown_404(self):
        status, _ = self._get("/nope.json")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
