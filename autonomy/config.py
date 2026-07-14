"""Configuration and whitelist handling for the additive autonomy gateway."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_MAP_CONFIG = PACKAGE_ROOT / "config" / "maps.json"
DEFAULT_ROUTE_CONFIG = PACKAGE_ROOT / "config" / "routes.json"


@dataclass(frozen=True)
class MapInfo:
    map_id: str
    name: str
    yaml_path: str
    pgm_path: str
    description: str

    def as_dict(self) -> dict[str, Any]:
        yaml_file = Path(self.yaml_path)
        pgm_file = Path(self.pgm_path)
        return {
            "id": self.map_id,
            "name": self.name,
            "yaml": self.yaml_path,
            "pgm": self.pgm_path,
            "description": self.description,
            "available": yaml_file.is_file() and pgm_file.is_file(),
            "yaml_exists": yaml_file.is_file(),
            "pgm_exists": pgm_file.is_file(),
        }


class ConfigError(ValueError):
    """Raised when a whitelist configuration is invalid."""


class Registry:
    """Read-only map and route registry.

    User input is always an ID.  Arbitrary filesystem paths are never accepted
    through the HTTP API, which keeps map loading bounded to the checked-in
    whitelist.
    """

    def __init__(
        self,
        map_file: str | os.PathLike[str] = DEFAULT_MAP_CONFIG,
        route_file: str | os.PathLike[str] = DEFAULT_ROUTE_CONFIG,
    ) -> None:
        self.map_file = Path(map_file)
        self.route_file = Path(route_file)
        self.maps = self._load_maps()
        self.routes = self._load_json(self.route_file)
        self._validate_routes()

    @staticmethod
    def _load_json(path: Path) -> Any:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"invalid configuration: {path}") from exc

    def _load_maps(self) -> dict[str, MapInfo]:
        raw = self._load_json(self.map_file)
        if not isinstance(raw, list):
            raise ConfigError("maps.json must contain a list")
        result: dict[str, MapInfo] = {}
        for item in raw:
            try:
                map_info = MapInfo(
                    map_id=str(item["id"]),
                    name=str(item["name"]),
                    yaml_path=str(item["yaml"]),
                    pgm_path=str(item["pgm"]),
                    description=str(item.get("description", "")),
                )
            except (KeyError, TypeError) as exc:
                raise ConfigError(f"invalid map entry: {item!r}") from exc
            if not map_info.map_id or map_info.map_id in result:
                raise ConfigError(f"duplicate or empty map id: {map_info.map_id!r}")
            result[map_info.map_id] = map_info
        return result

    def _validate_routes(self) -> None:
        if not isinstance(self.routes, dict):
            raise ConfigError("routes.json must contain an object")
        for route_id, route in self.routes.items():
            if not isinstance(route, dict):
                raise ConfigError(f"invalid route: {route_id}")
            map_id = route.get("map")
            if map_id not in self.maps:
                raise ConfigError(f"route {route_id} references unknown map {map_id!r}")
            waypoints = route.get("waypoints", [])
            if not isinstance(waypoints, list):
                raise ConfigError(f"route {route_id} waypoints must be a list")
            for point in waypoints:
                if not all(key in point for key in ("x", "y", "yaw")):
                    raise ConfigError(f"route {route_id} has incomplete waypoint")

    def list_maps(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.maps.values()]

    def get_map(self, map_id: str) -> MapInfo:
        try:
            return self.maps[map_id]
        except KeyError as exc:
            raise ConfigError(f"unknown map: {map_id}") from exc

    def list_routes(self) -> list[dict[str, Any]]:
        result = []
        for route_id, route in self.routes.items():
            result.append(
                {
                    "id": route_id,
                    "name": route.get("name", route_id),
                    "map": route["map"],
                    "enabled": bool(route.get("enabled", False)),
                    "description": route.get("description", ""),
                    "waypoint_count": len(route.get("waypoints", [])),
                }
            )
        return result

    def get_route(self, route_id: str) -> dict[str, Any]:
        try:
            return self.routes[route_id]
        except KeyError as exc:
            raise ConfigError(f"unknown route: {route_id}") from exc
