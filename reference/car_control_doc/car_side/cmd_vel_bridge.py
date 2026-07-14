#!/usr/bin/env python3
"""Bridge: ROS2 /cmd_vel → TCP proxy → Rosmaster → MCU

Runs inside Docker (host network). Subscribes to /cmd_vel and forwards
as joystick commands (TYPE=0x10) to the TCP proxy on port 6001.
"""

import socket
import threading
import time
import sys

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


# Protocol constants (must match Rosmaster protocol)
CMD_JOYSTICK = "10"
MAX_LINEAR = 0.4    # m/s, matches laser param "linear"
MAX_ANGULAR = 1.2   # rad/s, matches laser param "angular"


def to_hex(val):
    """Convert -100..100 to unsigned hex string (2 chars)."""
    v = int(round(val))
    if v < -100:
        v = -100
    elif v > 100:
        v = 100
    if v < 0:
        v += 256
    return f"{v:02X}"


def encode_joystick(x, y):
    """Encode joystick command in TEXT hex format: $01 TYPE SIZE DATA CKSUM #

    Protocol format (matching Android CarEncode.java):
    - SIZE = hex string length of INFO + 2
    - CHECKSUM = sum of all paired hex bytes in "01"+TYPE+SIZE+INFO, % 256
    """
    sx = to_hex(x)
    sy = to_hex(y)
    info = sx + sy                      # e.g. "5000"
    size = len(info) + 2                # hex chars + 2
    code = f"01{CMD_JOYSTICK}{size:02X}{info}"
    cksum = 0
    for i in range(0, len(code), 2):
        cksum = (cksum + int(code[i:i+2], 16)) & 0xFF
    return f"${code}{cksum:02X}#".encode()


class CmdVelBridge(Node):
    def __init__(self, host="127.0.0.1", port=6001):
        super().__init__("cmd_vel_bridge")
        self.host = host
        self.port = port
        self.sock = None
        self.lock = threading.Lock()
        self.running = True
        self._last_cmd_time = time.time()
        self._stopped_sent = False

        self._connect()
        self.sub = self.create_subscription(Twist, "/cmd_vel", self._on_cmd_vel, 10)
        # Safety: if no /cmd_vel for 1s, send stop
        self._safety_timer = self.create_timer(0.5, self._safety_check)
        self.get_logger().info(f"Bridge ready → {host}:{port}")

    def _safety_check(self):
        """Send stop if no /cmd_vel received for 2 seconds (prevents runaway)."""
        if time.time() - self._last_cmd_time > 2.0 and not self._stopped_sent:
            pkt = encode_joystick(0, 0)
            self._send(pkt)
            self._stopped_sent = True
            self.get_logger().warn("Safety stop: no /cmd_vel for >2s")

    def _connect(self):
        """Connect to TCP proxy, retry on failure."""
        while self.running:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3)
                self.sock.connect((self.host, self.port))
                self.sock.settimeout(None)
                self.get_logger().info(f"Connected to proxy {self.host}:{self.port}")
                return
            except Exception as e:
                self.get_logger().warn(f"Proxy connect failed: {e}, retrying...")
                time.sleep(2)

    def _send(self, data):
        """Send raw bytes to proxy."""
        with self.lock:
            if self.sock:
                try:
                    self.sock.send(data)
                except Exception:
                    self.get_logger().warn("Send failed, reconnecting...")
                    self._connect()

    _msg_count = 0

    def _on_cmd_vel(self, msg: Twist):
        """Convert Twist → joystick command → TCP."""
        self._msg_count += 1
        self._last_cmd_time = time.time()
        self._stopped_sent = False
        x = msg.angular.z / MAX_ANGULAR * 100.0    # rotation → X
        y = msg.linear.x / MAX_LINEAR * 100.0      # forward → Y
        if self._msg_count <= 3 or self._msg_count % 20 == 0:
            self.get_logger().info(f"CMD #{self._msg_count}: x={y:.0f}% y={x:.0f}% (lin={msg.linear.x:.2f} ang={msg.angular.z:.2f})")
        pkt = encode_joystick(x, y)
        self._send(pkt)

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()


def main():
    rclpy.init()
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 6001
    bridge = CmdVelBridge(host=host, port=port)
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        bridge.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
