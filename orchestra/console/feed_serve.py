"""out/ 静态服务（stdlib only）：GET /messages.json 前按 messages.md mtime 热重。

v2：同端口兼服 ui/（自研浅色控制台）；八产物路径不变。
"""
from __future__ import annotations

import functools
import json
import mimetypes
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


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
                    self.server._messages_mtime = mtime  # 记录观测 mtime，坏文件不反复重解析
            return self.server._messages_cache

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _try_ui(self, path: str) -> bool:
        ui_dir: Path = self.server.ui_dir  # type: ignore[attr-defined]
        if not ui_dir.is_dir():
            return False
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        if not rel or ".." in rel.split("/"):
            return False
        target = (ui_dir / rel).resolve()
        try:
            target.relative_to(ui_dir.resolve())
        except ValueError:
            return False
        if not target.is_file():
            return False
        data = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in (
            "application/javascript",
            "application/json",
            "image/svg+xml",
        ):
            ctype = f"{ctype}; charset=utf-8"
        self._send_bytes(data, ctype)
        return True

    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/messages.json":
            body = self._refresh_messages()
            self._send_bytes(body, "application/json; charset=utf-8")
            return
        # out/ 八产物优先；其余回落 ui/（自研控制台）
        out_candidate = Path(self.directory) / path.lstrip("/")
        if path not in ("/", "/index.html") and out_candidate.is_file():
            return super().do_GET()
        if self._try_ui(path):
            return
        if path not in ("/", "/index.html") and path.startswith("/"):
            # 保持原有 out 404 行为
            return super().do_GET()
        self.send_error(404, "Not Found")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        # 安静一点：保留默认也可；测试不依赖日志
        super().log_message(fmt, *args)


def make_server(out_dir: Path, bind: str = "127.0.0.1",
                port: int = 3100,
                ui_dir: Path | None = None) -> ThreadingHTTPServer:
    out_dir.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(FeedHandler, directory=str(out_dir))
    server = ThreadingHTTPServer((bind, port), handler)
    server.console_dir = out_dir.parent  # type: ignore[attr-defined]
    server.ui_dir = Path(ui_dir) if ui_dir else (out_dir.parent / "ui")  # type: ignore[attr-defined]
    server._messages_mtime = 0.0  # type: ignore[attr-defined]
    server._messages_cache = None  # type: ignore[attr-defined]
    server._messages_lock = threading.Lock()  # type: ignore[attr-defined]
    return server
