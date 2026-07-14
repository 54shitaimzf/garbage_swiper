"""Thread-safe mission state machine for the additive HTTP gateway."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from .adapters import AdapterError, MockAdapter, Ros2Adapter
from .config import ConfigError, Registry


class MissionError(ValueError):
    """A client-request or safe-state error."""


class MissionController:
    def __init__(
        self,
        registry: Registry | None = None,
        mode: str = "mock",
        mapping_output_dir: str | Path = "/tmp/icar_maps_generated",
        mock_duration_sec: float = 1.0,
    ) -> None:
        self.registry = registry or Registry()
        self.mode = mode.lower().strip()
        if self.mode not in {"mock", "ros2"}:
            raise MissionError("mode must be mock or ros2")
        self.mapping_output_dir = Path(mapping_output_dir)
        self._lock = threading.RLock()
        self._state = "idle"
        self._selected_map: str | None = None
        self._selected_route: str | None = None
        self._mission_id: str | None = None
        self._mission_kind: str | None = None
        self._started_at: float | None = None
        self._last_error: str | None = None
        self._mapping_state = "idle"
        self._mapping_started_at: float | None = None
        if self.mode == "mock":
            self.adapter = MockAdapter(mock_duration_sec, self._adapter_state)
        else:
            self.adapter = Ros2Adapter(self._adapter_state)

    def _adapter_state(self, state: str, message: str) -> None:
        with self._lock:
            if state == "succeeded":
                self._state = "succeeded"
                self._last_error = None
            elif state == "error":
                self._state = "error"
                self._last_error = message
            self._mission_id = message if state == "succeeded" else self._mission_id

    def _refresh(self) -> None:
        if self._state == "running" and self._mission_kind == "home":
            # Home is intentionally a safe no-motion placeholder in mock mode.
            return

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            adapter_status = self.adapter.status().as_dict()
            return {
                "ok": True,
                "mode": self.mode,
                "state": self._state,
                "selected_map": self._selected_map,
                "selected_route": self._selected_route,
                "mission_id": self._mission_id,
                "mission_kind": self._mission_kind,
                "started_at": self._started_at,
                "last_error": self._last_error,
                "adapter": adapter_status,
                "mapping": {
                    "state": self._mapping_state,
                    "started_at": self._mapping_started_at,
                },
                "safe_to_use": self._state in {"idle", "succeeded", "stopped", "error"},
                "legacy_gateway": {
                    "port": 8081,
                    "untouched": True,
                    "note": "自主服务不会修改旧手动网关",
                },
            }

    def list_maps(self) -> list[dict[str, Any]]:
        return self.registry.list_maps()

    def list_routes(self) -> list[dict[str, Any]]:
        return self.registry.list_routes()

    def activate(self) -> dict[str, Any]:
        with self._lock:
            if self._state == "running":
                raise MissionError("cannot activate while a mission is running")
            try:
                self.adapter.activate()
            except AdapterError as exc:
                self._state = "error"
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._state = "ready"
            self._last_error = None
            return self.status()

    def deactivate(self) -> dict[str, Any]:
        with self._lock:
            try:
                self.adapter.cancel()
                self.adapter.deactivate()
            except AdapterError as exc:
                self._state = "error"
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._state = "idle"
            self._mission_id = None
            self._mission_kind = None
            self._started_at = None
            return self.status()

    def select_map(self, map_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                self.registry.get_map(map_id)
            except ConfigError as exc:
                raise MissionError(str(exc)) from exc
            if self._state == "running":
                raise MissionError("cannot change map while a mission is running")
            self._selected_map = map_id
            return self.status()

    def start(self, route_id: str) -> dict[str, Any]:
        with self._lock:
            if self._state != "ready":
                raise MissionError("activate autonomy before starting a mission")
            try:
                route = self.registry.get_route(route_id)
            except ConfigError as exc:
                raise MissionError(str(exc)) from exc
            if not route.get("enabled", False):
                raise MissionError("route is not enabled; calibrate safe waypoints first")
            if not route.get("waypoints"):
                raise MissionError("route has no calibrated waypoints")
            route_map = route["map"]
            if self._selected_map != route_map:
                raise MissionError(f"route requires map {route_map}")
            if self.mode == "ros2" and not self.registry.get_map(route_map).as_dict()["available"]:
                raise MissionError("selected map files are unavailable on this host")
            self._selected_route = route_id
            self._mission_id = f"mission-{int(time.time() * 1000)}"
            self._mission_kind = "route"
            self._started_at = time.time()
            self._last_error = None
            try:
                self.adapter.start(self._mission_id, route["waypoints"])
            except AdapterError as exc:
                self._state = "error"
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._state = "running"
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            try:
                self.adapter.cancel()
            except AdapterError as exc:
                self._state = "error"
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._state = "stopped"
            self._last_error = None
            return self.status()

    def home(self) -> dict[str, Any]:
        with self._lock:
            if self._state != "ready":
                raise MissionError("activate autonomy before returning home")
            try:
                self.adapter.home()
            except AdapterError as exc:
                self._state = "error"
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._mission_id = f"home-{int(time.time() * 1000)}"
            self._mission_kind = "home"
            self._started_at = time.time()
            self._state = "running"
            return self.status()

    def mapping_start(self) -> dict[str, Any]:
        with self._lock:
            if self._state not in {"ready", "idle"}:
                raise MissionError("stop the mission before starting SLAM")
            try:
                self.adapter.start_mapping()
            except AdapterError as exc:
                self._state = "error" if self.mode == "ros2" else self._state
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._mapping_state = "running"
            self._mapping_started_at = time.time()
            return self.status()

    def mapping_stop(self) -> dict[str, Any]:
        with self._lock:
            try:
                self.adapter.stop_mapping()
            except AdapterError as exc:
                self._last_error = str(exc)
                raise MissionError(str(exc)) from exc
            self._mapping_state = "stopped"
            return self.status()

    def mapping_save(self, map_id: str) -> dict[str, Any]:
        with self._lock:
            if self._mapping_state != "stopped":
                raise MissionError("stop SLAM before saving a map")
            if not map_id or "/" in map_id or "\\" in map_id or map_id in {".", ".."}:
                raise MissionError("map id contains unsafe characters")
            output_dir = self.mapping_output_dir.resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            yaml_path = output_dir / f"{map_id}.yaml"
            pgm_path = output_dir / f"{map_id}.pgm"
            if yaml_path.exists() or pgm_path.exists():
                raise MissionError("refusing to overwrite an existing generated map")
            if self.mode == "mock":
                yaml_path.write_text(
                    "image: %s.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n"
                    % map_id,
                    encoding="utf-8",
                )
                pgm_path.write_bytes(b"P5\n1 1\n255\n\xFF")
            else:
                raise MissionError("ROS2 map saver is not connected until SLAM is verified")
            self._mapping_state = "saved"
            return {**self.status(), "saved_map": {"id": map_id, "yaml": str(yaml_path), "pgm": str(pgm_path)}}

    def shutdown(self) -> None:
        with self._lock:
            try:
                self.adapter.shutdown()
            except Exception:
                pass
