"""out/ 静态服务（stdlib only）：GET /messages.json 前按 messages.md mtime 热重。"""
from __future__ import annotations

import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class FeedHandler(SimpleHTTPRequestHandler):
    def _refresh_messages(self) -> bytes:
        empty = {"latest": [], "pending": [], "alerts": []}
        src = self.server.console_dir / "messages.md"
        try:
            mtime = src.stat().st_mtime
        except OSError:
            return json.dumps(empty, ensure_ascii=False, indent=2).encode("utf-8")
        with self.server._messages_lock:
            if (self.server._messages_cache is None
                    or mtime != self.server._messages_mtime):
                try:
                    from feed_messages import parse_messages
                    data = parse_messages(src.read_text(encoding="utf-8"))
                    self.server._messages_cache = json.dumps(
                        data, ensure_ascii=False, indent=2).encode("utf-8")
                    self.server._messages_mtime = mtime
                except (OSError, ValueError):
                    self.server._messages_cache = json.dumps(
                        empty, ensure_ascii=False, indent=2).encode("utf-8")
                    self.server._messages_mtime = 0.0
            return self.server._messages_cache

    def do_GET(self):  # noqa: N802
        if self.path.split("?", 1)[0] == "/messages.json":
            body = self._refresh_messages()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def make_server(out_dir: Path, bind: str = "127.0.0.1",
                port: int = 3100) -> ThreadingHTTPServer:
    out_dir.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(FeedHandler, directory=str(out_dir))
    server = ThreadingHTTPServer((bind, port), handler)
    server.console_dir = out_dir.parent  # type: ignore[attr-defined]
    server._messages_mtime = 0.0  # type: ignore[attr-defined]
    server._messages_cache = None  # type: ignore[attr-defined]
    server._messages_lock = threading.Lock()  # type: ignore[attr-defined]
    return server
