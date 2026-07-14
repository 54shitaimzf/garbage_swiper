#!/usr/bin/env python3
"""Publish read-only health for the official sensor topics.

This node never publishes /cmd_vel and therefore can be used as a first ROS2
bring-up check before navigation is enabled.
"""

from __future__ import annotations

import json
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage


class SensorHealthNode(Node):
    def __init__(self) -> None:
        super().__init__("icar_sensor_health")
        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("tf_topic", "/tf")
        self.declare_parameter("image_topic", "/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/depth/image_raw")
        self.declare_parameter("timeout_sec", 3.0)
        self.declare_parameter("require_depth", True)

        self.timeout_sec = float(self.get_parameter("timeout_sec").value)
        self.require_depth = bool(self.get_parameter("require_depth").value)
        self.last_seen: dict[str, float | None] = {"scan": None, "odom": None, "tf": None, "image": None, "depth": None}
        self.counts = {key: 0 for key in self.last_seen}

        self.health_pub = self.create_publisher(String, "/icar/autonomy/sensor_health", 10)
        self.create_subscription(LaserScan, str(self.get_parameter("scan_topic").value), lambda _: self._seen("scan"), 10)
        self.create_subscription(Odometry, str(self.get_parameter("odom_topic").value), lambda _: self._seen("odom"), 10)
        self.create_subscription(TFMessage, str(self.get_parameter("tf_topic").value), lambda _: self._seen("tf"), 10)
        self.create_subscription(Image, str(self.get_parameter("image_topic").value), lambda _: self._seen("image"), 10)
        self.create_subscription(Image, str(self.get_parameter("depth_topic").value), lambda _: self._seen("depth"), 10)
        self.create_timer(1.0, self._publish_health)

    def _seen(self, name: str) -> None:
        self.last_seen[name] = time.monotonic()
        self.counts[name] += 1

    def _publish_health(self) -> None:
        now = time.monotonic()
        required = ["scan", "odom", "tf", "image"] + (["depth"] if self.require_depth else [])
        topics = {}
        for name, stamp in self.last_seen.items():
            age = None if stamp is None else round(now - stamp, 3)
            topics[name] = {"ok": age is not None and age <= self.timeout_sec, "age_sec": age, "count": self.counts[name]}
        healthy = all(topics[name]["ok"] for name in required)
        message = String()
        message.data = json.dumps(
            {"ok": healthy, "required": required, "topics": topics, "timestamp": time.time()},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.health_pub.publish(message)


def main() -> None:
    rclpy.init()
    node = SensorHealthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
