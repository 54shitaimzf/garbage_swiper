"""Standalone HTTP gateway for additive autonomous tasks on port 8082."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .controller import MissionController, MissionError


PWA_ROOT = Path(__file__).resolve().parent / "pwa"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class AutonomyRequestHandler(BaseHTTPRequestHandler):
    server_version = "ICARAutonomy/0.1"

    @property
    def controller(self) -> MissionController:
        return self.server.controller  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the service usable under nohup without leaking request bodies.
        print("[autonomy] " + (fmt % args), flush=True)

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._send_json({"ok": False, "error": message}, status)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 64 * 1024:
            raise MissionError("request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MissionError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise MissionError("request body must be a JSON object")
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/healthz":
                self._send_json({"ok": True, "service": "autonomy", "port": 8082, "legacy_port": 8081})
            elif path == "/api/maps":
                self._send_json({"ok": True, "maps": self.controller.list_maps()})
            elif path == "/api/routes":
                self._send_json({"ok": True, "routes": self.controller.list_routes()})
            elif path == "/api/autonomy/status":
                self._send_json(self.controller.status())
            elif path == "/":
                self._serve_static("index.html")
            elif path.startswith("/"):
                self._serve_static(path.lstrip("/"))
            else:
                self._send_error_json("not found", HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            self._send_error_json("not found", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # defensive boundary for a long-running service
            self._send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def _serve_static(self, relative: str) -> None:
        candidate = (PWA_ROOT / relative).resolve()
        root = PWA_ROOT.resolve()
        if root not in candidate.parents and candidate != root:
            raise FileNotFoundError(relative)
        if not candidate.is_file():
            raise FileNotFoundError(relative)
        content = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".webmanifest":
            content_type = "application/manifest+json"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/autonomy/activate":
                result = self.controller.activate()
            elif path == "/api/autonomy/deactivate":
                result = self.controller.deactivate()
            elif path == "/api/mission/map":
                result = self.controller.select_map(str(body.get("map_id", "")))
            elif path == "/api/mission/start":
                result = self.controller.start(str(body.get("route_id", "")))
            elif path == "/api/mission/stop":
                result = self.controller.stop()
            elif path == "/api/mission/home":
                result = self.controller.home()
            elif path == "/api/mapping/start":
                result = self.controller.mapping_start()
            elif path == "/api/mapping/stop":
                result = self.controller.mapping_stop()
            elif path == "/api/mapping/save":
                result = self.controller.mapping_save(str(body.get("map_id", "")))
            else:
                self._send_error_json("not found", HTTPStatus.NOT_FOUND)
                return
            self._send_json(result)
        except MissionError as exc:
            self._send_error_json(str(exc), HTTPStatus.CONFLICT)
        except Exception as exc:
            self._send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)


class AutonomyHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], controller: MissionController) -> None:
        self.controller = controller
        super().__init__(address, AutonomyRequestHandler)


def build_controller(mode: str | None = None) -> MissionController:
    resolved_mode = (mode or os.getenv("AUTONOMY_MODE", "mock")).lower()
    output_dir = os.getenv("ICAR_MAPPING_OUTPUT_DIR", "/tmp/icar_maps_generated")
    duration = float(os.getenv("AUTONOMY_MOCK_DURATION_SEC", "1.0"))
    return MissionController(mode=resolved_mode, mapping_output_dir=output_dir, mock_duration_sec=duration)


def run(host: str = "0.0.0.0", port: int = 8082, mode: str | None = None) -> None:
    controller = build_controller(mode)
    server = AutonomyHTTPServer((host, port), controller)
    print(f"[autonomy] listening on http://{host}:{port} mode={controller.mode}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.shutdown()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("AUTONOMY_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("AUTONOMY_PORT", "8082")))
    parser.add_argument("--mode", choices=("mock", "ros2"), default=os.getenv("AUTONOMY_MODE", "mock"))
    args = parser.parse_args()
    run(args.host, args.port, args.mode)


if __name__ == "__main__":
    main()
