#!/usr/bin/env python3
"""ROS2: foreign object alarm + emergency stop using depth + detections."""

from __future__ import annotations

import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String
from vision_msgs.msg import Detection2DArray


class ForeignObjectAvoidance(Node):
    def __init__(self) -> None:
        super().__init__("foreign_object_avoidance")

        self.declare_parameter("detection_topic", "/detections")
        self.declare_parameter("depth_topic", "/camera/depth/image_raw")
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("stop_distance_m", 0.85)
        self.declare_parameter("min_bbox_height_ratio", 0.28)
        self.declare_parameter("image_height", 480.0)
        self.declare_parameter("conf_threshold", 0.35)
        self.declare_parameter("use_depth", True)
        self.declare_parameter("hold_stop_hz", 10.0)

        self.det_topic = self.get_parameter("detection_topic").get_parameter_value().string_value
        self.depth_topic = self.get_parameter("depth_topic").get_parameter_value().string_value
        self.cmd_topic = self.get_parameter("cmd_vel_topic").get_parameter_value().string_value
        self.stop_distance = self.get_parameter("stop_distance_m").get_parameter_value().double_value
        self.min_bbox_ratio = self.get_parameter("min_bbox_height_ratio").get_parameter_value().double_value
        self.image_height = self.get_parameter("image_height").get_parameter_value().double_value
        self.conf_threshold = self.get_parameter("conf_threshold").get_parameter_value().double_value
        self.use_depth = self.get_parameter("use_depth").get_parameter_value().bool_value
        hold_hz = self.get_parameter("hold_stop_hz").get_parameter_value().double_value

        self.bridge = CvBridge()
        self.latest_depth = None
        self.is_stopped = False
        self.last_alarm_msg = ""

        self.cmd_pub = self.create_publisher(Twist, self.cmd_topic, 10)
        self.alarm_pub = self.create_publisher(Bool, "/vision/alarm", 10)
        self.alarm_msg_pub = self.create_publisher(String, "/vision/alarm_msg", 10)

        self.create_subscription(Detection2DArray, self.det_topic, self.det_cb, 10)
        if self.use_depth:
            self.create_subscription(Image, self.depth_topic, self.depth_cb, 10)

        if hold_hz > 0:
            self.create_timer(1.0 / hold_hz, self._hold_stop_timer)

        self.get_logger().info(
            f"Avoidance ready. stop_distance={self.stop_distance}m, "
            f"bbox_ratio={self.min_bbox_ratio}, image_h={self.image_height}"
        )

    def _hold_stop_timer(self) -> None:
        if self.is_stopped:
            self.cmd_pub.publish(Twist())

    def depth_cb(self, msg: Image) -> None:
        self.latest_depth = msg

    def _depth_at(self, cx: float, cy: float) -> float | None:
        if self.latest_depth is None:
            return None
        enc = self.latest_depth.encoding.lower()
        try:
            if enc in ("16uc1", "mono16"):
                depth = self.bridge.imgmsg_to_cv2(self.latest_depth, desired_encoding="16UC1")
                x = int(max(0, min(depth.shape[1] - 1, cx)))
                y = int(max(0, min(depth.shape[0] - 1, cy)))
                val_mm = int(depth[y, x])
                if val_mm == 0:
                    return None
                return val_mm / 1000.0
            depth = self.bridge.imgmsg_to_cv2(self.latest_depth)
            x = int(max(0, min(depth.shape[1] - 1, cx)))
            y = int(max(0, min(depth.shape[0] - 1, cy)))
            val = float(depth[y, x])
            if val <= 0:
                return None
            return val / 1000.0 if val > 20 else val
        except Exception:
            return None

    def det_cb(self, msg: Detection2DArray) -> None:
        danger = False
        reasons = []

        for det in msg.detections:
            if not det.results:
                continue
            score = det.results[0].hypothesis.score
            if score < self.conf_threshold:
                continue
            name = det.results[0].hypothesis.class_id
            cx = det.bbox.center.x
            cy = det.bbox.center.y
            bbox_h_ratio = det.bbox.size_y / self.image_height if det.bbox.size_y > 0 else 0.0

            depth_m = self._depth_at(cx, cy) if self.use_depth else None
            close_by_depth = depth_m is not None and depth_m < self.stop_distance
            close_by_bbox = bbox_h_ratio >= self.min_bbox_ratio

            if close_by_depth or close_by_bbox:
                danger = True
                if depth_m is not None:
                    reasons.append(f"{name}@{depth_m:.2f}m")
                else:
                    reasons.append(f"{name}(near)")

        if danger:
            self._publish_stop(reasons)
        else:
            if self.is_stopped:
                self.get_logger().info("Path clear, stop released.")
                clear = Bool()
                clear.data = False
                self.alarm_pub.publish(clear)
                self.alarm_msg_pub.publish(String(data="CLEAR"))
            self.is_stopped = False
            self.last_alarm_msg = ""

    def _publish_stop(self, reasons: list[str]) -> None:
        twist = Twist()
        self.cmd_pub.publish(twist)

        alarm = Bool()
        alarm.data = True
        self.alarm_pub.publish(alarm)

        msg = String()
        msg.data = "ALARM: " + ", ".join(reasons)
        self.alarm_msg_pub.publish(msg)

        if msg.data != self.last_alarm_msg:
            self.get_logger().warn(msg.data)
            self.last_alarm_msg = msg.data
        self.is_stopped = True


def main() -> None:
    rclpy.init()
    node = ForeignObjectAvoidance()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
