#!/usr/bin/env python3
"""Read-only smoke checks for the legacy 8081 HTTP chain.

Motion, joystick direction, buzzer hearing, hotspot switching and emergency
stop remain physical acceptance checks. This script never sends a motion or
buzzer command and therefore cannot claim those checks passed automatically.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from time import time


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def get_json(base: str, path: str, timeout: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(base.rstrip("/") + path, timeout=timeout) as response:
            payload = response.read(256 * 1024)
            if response.status != 200:
                return False, f"HTTP {response.status}"
            json.loads(payload.decode("utf-8"))
            return True, "JSON response"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return False, str(exc)


def run(base: str, timeout: float = 3.0) -> dict:
    checks = []
    for name, path in (
        ("status", "/api/status"),
        ("yolo_latest", "/api/yolo/latest"),
    ):
        ok, detail = get_json(base, path, timeout)
        checks.append(Check(name, ok, detail))
    checks.append(Check("video", False, "requires a browser/MJPEG frame observation"))
    checks.append(Check("websocket", False, "requires browser WebSocket observation"))
    checks.append(Check("motion_and_joystick", False, "requires supervised physical test"))
    checks.append(Check("speed_and_stop", False, "requires supervised physical test"))
    checks.append(Check("buzzer_and_reconnect", False, "requires supervised physical test"))
    automated_ok = all(item.ok for item in checks[:2])
    return {
        "timestamp": time(),
        "base": base,
        "automated_ok": automated_ok,
        "manual_checks_required": [item.name for item in checks if not item.ok and item.name not in {"status", "yolo_latest"}],
        "checks": [asdict(item) for item in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://10.71.253.19:8081")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    result = run(args.base, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["automated_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
