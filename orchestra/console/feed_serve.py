"""out/ 静态服务（stdlib only）：GET /messages.json 前按 messages.md mtime 热重。"""
from __future__ import annotations

import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class FeedHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, console_dir=None, **kwargs):
        self.console_dir = Path(console_dir) if console_dir is not None else None
        self._messages_mtime = 0.0
        self._messages_cache = None
        super().__init__(*args, **kwargs)

    def _refresh_messages(self) -> bytes:
        empty = {"latest": [], "pending": [], "alerts": []}
        try:
            src = self.console_dir / "messages.md"
            mtime = src.stat().st_mtime
            if self._messages_cache is None or mtime != self._messages_mtime:
                from feed_messages import parse_messages
                data = parse_messages(src.read_text(encoding="utf-8"))
                self._messages_cache = json.dumps(
                    data, ensure_ascii=False, indent=2).encode("utf-8")
                self._messages_mtime = mtime
        except (OSError, ValueError):
            self._messages_cache = json.dumps(
                empty, ensure_ascii=False, indent=2).encode("utf-8")
            self._messages_mtime = 0.0
        return self._messages_cache

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
    handler = functools.partial(
        FeedHandler, directory=str(out_dir), console_dir=str(out_dir.parent))
    return ThreadingHTTPServer((bind, port), handler)
