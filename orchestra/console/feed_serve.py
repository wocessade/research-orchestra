"""out/ 静态服务（stdlib only）：GET /messages.json 前按 messages.md mtime 热重。

v2：同端口兼服 ui/（自研浅色控制台）；八产物路径不变。
个人日程写入：POST/PUT/DELETE /api/personal（只改 [[personal]]，不碰 system）。
"""
from __future__ import annotations

import functools
import json
import mimetypes
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


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

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or "0")
        if n > 16384:
            raise ValueError("payload too large")
        raw = self.rfile.read(n) if n else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON 必须是对象")
        return data

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

    def _personal_list(self, sched: dict) -> list:
        from feed_schedule import personal_public
        return [personal_public(p) for p in sched["personal"]]

    def _handle_personal(self, method: str) -> None:
        from feed_schedule import (
            add_personal,
            delete_personal,
            parse_schedule,
            rebuild_personal_ics,
            toggle_personal_done,
            update_personal,
            write_schedule,
        )
        src = self.server.console_dir / "console-schedule.toml"
        with self.server._schedule_lock:
            try:
                sched = parse_schedule(src.read_text(encoding="utf-8"))
            except FileNotFoundError:
                self._send_json({"error": "缺少 console-schedule.toml"}, 500)
                return
            except (OSError, ValueError) as exc:
                self._send_json({"error": str(exc)}, 500)
                return
            if method == "GET":
                self._send_json({"personal": self._personal_list(sched)})
                return
            try:
                if method == "POST":
                    sched = add_personal(sched, self._read_json())
                elif method == "PUT":
                    body = self._read_json()
                    ident = str(body.get("id") or "")
                    if not ident:
                        self._send_json({"error": "缺 id"}, 400)
                        return
                    sched = update_personal(sched, ident, body)
                elif method == "DELETE":
                    ident = (parse_qs(urlparse(self.path).query).get("id") or [""])[0]
                    if not ident:
                        self._send_json({"error": "缺 id"}, 400)
                        return
                    sched = delete_personal(sched, ident)
                else:
                    self._send_json({"error": "method"}, 405)
                    return
                write_schedule(src, sched)
                rebuild_personal_ics(Path(self.directory), sched)
            except KeyError:
                self._send_json({"error": "事件不存在"}, 404)
                return
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, 400)
                return
        self._send_json({"ok": True, "personal": self._personal_list(sched)})

    def _handle_personal_done(self) -> None:
        from feed_schedule import (
            parse_schedule,
            rebuild_personal_ics,
            toggle_personal_done,
            write_schedule,
        )
        src = self.server.console_dir / "console-schedule.toml"
        with self.server._schedule_lock:
            try:
                sched = parse_schedule(src.read_text(encoding="utf-8"))
                body = self._read_json()
                ident = str(body.get("id") or "")
                if not ident:
                    self._send_json({"error": "缺 id"}, 400)
                    return
                sched = toggle_personal_done(sched, ident, body.get("date"))
                write_schedule(src, sched)
                rebuild_personal_ics(Path(self.directory), sched)
            except KeyError:
                self._send_json({"error": "事件不存在"}, 404)
                return
            except FileNotFoundError:
                self._send_json({"error": "缺少 console-schedule.toml"}, 500)
                return
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, 400)
                return
        self._send_json({"ok": True, "personal": self._personal_list(sched)})

    def _handle_radar(self) -> None:
        from feed_radar import find_radar
        qs = parse_qs(urlparse(self.path).query)
        date = (qs.get("date") or [None])[0]
        root = getattr(self.server, "results_root", None)
        if root is None:
            root = self.server.console_dir.parent / "results"
        self._send_json(find_radar(Path(root), date))

    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/messages.json":
            body = self._refresh_messages()
            self._send_bytes(body, "application/json; charset=utf-8")
            return
        if path == "/api/personal":
            self._handle_personal("GET")
            return
        if path == "/api/radar":
            self._handle_radar()
            return
        # out/ 八产物优先；其余回落 ui/（自研控制台）
        out_candidate = Path(self.directory) / path.lstrip("/")
        if path not in ("/", "/index.html") and out_candidate.is_file():
            return super().do_GET()
        if self._try_ui(path):
            return
        if path not in ("/", "/index.html") and path.startswith("/"):
            return super().do_GET()
        self.send_error(404, "Not Found")

    def do_POST(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/api/personal":
            self._handle_personal("POST")
            return
        if path == "/api/personal/done":
            self._handle_personal_done()
            return
        self.send_error(404, "Not Found")

    def do_PUT(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/api/personal":
            self._handle_personal("PUT")
            return
        self.send_error(404, "Not Found")

    def do_DELETE(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/api/personal":
            self._handle_personal("DELETE")
            return
        self.send_error(404, "Not Found")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        super().log_message(fmt, *args)


def make_server(out_dir: Path, bind: str = "127.0.0.1",
                port: int = 3100,
                ui_dir: Path | None = None,
                results_root: Path | None = None) -> ThreadingHTTPServer:
    out_dir.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(FeedHandler, directory=str(out_dir))
    server = ThreadingHTTPServer((bind, port), handler)
    server.console_dir = out_dir.parent  # type: ignore[attr-defined]
    server.ui_dir = Path(ui_dir) if ui_dir else (out_dir.parent / "ui")  # type: ignore[attr-defined]
    server.results_root = Path(results_root) if results_root else (
        out_dir.parent.parent / "results")  # type: ignore[attr-defined]
    server._messages_mtime = 0.0  # type: ignore[attr-defined]
    server._messages_cache = None  # type: ignore[attr-defined]
    server._messages_lock = threading.Lock()  # type: ignore[attr-defined]
    server._schedule_lock = threading.Lock()  # type: ignore[attr-defined]
    return server
