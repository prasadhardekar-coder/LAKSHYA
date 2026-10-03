from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


class DashboardServer:
    """Serve the local dashboard and the controller's latest live data."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        web_root: str | Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.web_root = Path(web_root) if web_root else Path(__file__).resolve().parent.parent / "web"
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {}
        self._frame = b""
        self._last_publish = 0.0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        if self._server is None:
            return f"http://{self.host}:{self.port}/"
        return f"http://{self.host}:{self._server.server_port}/"

    def start(self) -> str:
        dashboard = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                request = urlsplit(self.path)
                if request.path in ("/", "/index.html"):
                    dashboard._serve_file(self, dashboard.web_root / "index.html")
                elif request.path == "/api/state":
                    self._send_json(dashboard._get_state())
                elif request.path == "/api/frame.jpg":
                    with dashboard._lock:
                        frame = dashboard._frame
                    if not frame:
                        self.send_error(503, "No camera frame received yet")
                        return
                    download = "download" in parse_qs(request.query)
                    headers = {"Content-Disposition": "attachment; filename=tracking-frame.jpg"} if download else None
                    self._send_bytes(frame, "image/jpeg", headers)
                else:
                    self.send_error(404)

            def _send_json(self, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self._send_bytes(body, "application/json; charset=utf-8")

            def _send_bytes(
                self,
                body: bytes,
                content_type: str,
                extra_headers: dict[str, str] | None = None,
            ) -> None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                if extra_headers:
                    for name, value in extra_headers.items():
                        self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: Any) -> None:
                pass

        class LocalThreadingHTTPServer(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = LocalThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="tracking-dashboard-http",
            daemon=True,
        )
        self._thread.start()
        return self.url

    def publish(self, state: dict[str, Any], frame_jpeg: bytes) -> None:
        with self._lock:
            self._state = dict(state)
            self._frame = bytes(frame_jpeg)
            self._last_publish = time.monotonic()

    def _get_state(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state)
            updated = self._last_publish

        state["controller_connected"] = updated > 0.0
        state["godot_connected"] = updated > 0.0 and time.monotonic() - updated < 1.25
        return state

    @staticmethod
    def _serve_file(handler: BaseHTTPRequestHandler, file_path: Path) -> None:
        try:
            body = file_path.read_bytes()
        except OSError:
            handler.send_error(404, "Dashboard file not found")
            return

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
