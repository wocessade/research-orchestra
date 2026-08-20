import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

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

    def test_unknown_404(self):
        status, _ = self._get("/nope.json")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
