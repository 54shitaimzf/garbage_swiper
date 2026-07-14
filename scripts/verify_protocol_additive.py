#!/usr/bin/env python3
"""Additive golden-frame check for the live official TCP representation.

The legacy protocol scripts are left untouched. This check documents the
reference length rule used by the current 8081 gateway without changing its
runtime implementation.
"""


def frame(type_code: str, data: str = "") -> str:
    body = "01" + type_code + f"{len(data) + 2:02X}" + data
    checksum = sum(int(body[i : i + 2], 16) for i in range(0, len(body), 2)) & 0xFF
    return f"${body}{checksum:02X}#"


def signed_byte(value: int) -> int:
    value = max(-100, min(100, value))
    return value if value >= 0 else value + 256


def joystick(x: int, y: int) -> str:
    return frame("10", f"{signed_byte(x):02X}{signed_byte(y):02X}")


assert joystick(80, 0) == "$011006500067#"
assert joystick(-100, 0) == "$0110069C00B3#"
assert frame("15", "07") == "$0115040721#"
print("additive protocol golden checks: PASS")
