#!/usr/bin/env python3
"""Protocol regression checks copied from the official reference implementation."""


def frame(type_code, data=""):
    body = "01" + type_code + f"{len(data) // 2 + 2:02X}" + data
    checksum = sum(int(body[i:i + 2], 16) for i in range(0, len(body), 2)) & 0xFF
    return f"${body}{checksum:02X}#"


def signed_byte(value):
    value = max(-100, min(100, value))
    return value if value >= 0 else value + 256


def joystick(x, y):
    return frame("10", f"{signed_byte(x):02X}{signed_byte(y):02X}")


assert joystick(80, 0) == "$011006500067#"
assert joystick(-100, 0) == "$0110069C0063#"
assert frame("15", "07") == "$011504070C#"
print("protocol checks: PASS")
