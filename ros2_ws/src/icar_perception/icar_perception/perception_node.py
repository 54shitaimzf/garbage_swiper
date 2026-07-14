#!/usr/bin/env python3
"""icar_perception: YOLO + TensorRT detection, publishes /detections."""

from __future__ import annotations

import os
import time

import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

DEFAULT_CLASS_LABELS = [
    "drink_white",
    "drink_red",
    "drink_green",
    "backpack",
    "tea_box",
]


class PerceptionNode(Node):
    def __init__(self) -> None:
        super().__init__("perception_node")

        self.declare_parameter("use_sim_detection", False)
        self.declare_parameter("model_path", "/root/models/yolo.engine")
        self.declare_parameter("image_topic", "/image_raw")
        self.declare_parameter("detection_topic", "/detections")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("input_size", 640)
        self.declare_parameter("detection_rate_hz", 10.0)
        self.declare_parameter("class_labels", DEFAULT_CLASS_LABELS)
        self.declare_parameter("publish_image", False)
        self.declare_parameter("fps_log_interval_sec", 5.0)

        self.use_sim = self.get_parameter("use_sim_detection").get_parameter_value().bool_value
        model_path = self.get_parameter("model_path").get_parameter_value().string_value
        self.image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        self.detection_topic = self.get_parameter("detection_topic").get_parameter_value().string_value
        self.conf_threshold = self.get_parameter("confidence_threshold").get_parameter_value().double_value
        self.imgsz = int(self.get_parameter("input_size").get_parameter_value().integer_value)
        rate_hz = self.get_parameter("detection_rate_hz").get_parameter_value().double_value
        self.min_infer_interval = 1.0 / rate_hz if rate_hz > 0 else 0.0
        self.publish_image = self.get_parameter("publish_image").get_parameter_value().bool_value
        self.fps_log_interval = self.get_parameter("fps_log_interval_sec").get_parameter_value().double_value
        self.class_labels = list(self.get_parameter("class_labels").get_parameter_value().string_array_value)
        if not self.class_labels:
            self.class_labels = DEFAULT_CLASS_LABELS

        self.bridge = CvBridge()
        self.model = None
        self._frame_count = 0
        self._fps_window_start = time.monotonic()
        self._last_infer_time = 0.0

        if self.use_sim:
            self.get_logger().warn("SIM mode: publishing fake detections (no model loaded)")
        else:
            if YOLO is None:
                raise ImportError("pip3 install ultralytics")
            if not os.path.exists(model_path):
                self.get_logger().error(f"Model not found: {model_path}")
                raise FileNotFoundError(model_path)
            ext = os.path.splitext(model_path)[1].lower()
            self.get_logger().info(f"Loading {ext} model: {model_path}")
            self.model = YOLO(model_path)

        self.det_pub = self.create_publisher(Detection2DArray, self.detection_topic, 10)
        self.label_pub = self.create_publisher(String, "/vision/foreign_objects/summary", 10)
        self.image_pub = self.create_publisher(Image, "/vision/foreign_objects/image", 10)
        self.sub = self.create_subscription(Image, self.image_topic, self.image_callback, 10)
        self.get_logger().info(
            f"perception_node ready | in={self.image_topic} out={self.detection_topic} "
            f"sim={self.use_sim} rate={rate_hz}Hz labels={self.class_labels}"
        )

    def image_callback(self, msg: Image) -> None:
        now = time.monotonic()
        if self.min_infer_interval > 0 and (now - self._last_infer_time) < self.min_infer_interval:
            return
        self._last_infer_time = now

        if self.use_sim:
            detections = self._sim_detections(msg.header)
            self.det_pub.publish(detections)
            sim_name = self.class_labels[0] if self.class_labels else "foreign_object"
            self.label_pub.publish(String(data=f"detected: {sim_name} (sim)"))
            self._update_fps()
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        results = self.model.predict(
            frame, conf=self.conf_threshold, verbose=False, imgsz=self.imgsz
        )
        detections = self._to_detection_array(results[0], msg.header)
        self.det_pub.publish(detections)

        summary = self._build_summary(detections)
        self.label_pub.publish(String(data=summary))

        if self.publish_image:
            annotated = results[0].plot()
            out_msg = self.bridge.cv2_to_imgmsg(annotated, encoding="bgr8")
            out_msg.header = msg.header
            self.image_pub.publish(out_msg)

        if summary:
            self.get_logger().info(summary, throttle_duration_sec=2.0)
        self._update_fps()

    def _sim_detections(self, header) -> Detection2DArray:
        arr = Detection2DArray()
        arr.header = header
        det = Detection2D()
        det.header = header
        det.bbox.center.x = 320.0
        det.bbox.center.y = 240.0
        det.bbox.size_x = 120.0
        det.bbox.size_y = 180.0
        hyp = ObjectHypothesisWithPose()
        hyp.hypothesis.class_id = self.class_labels[0] if self.class_labels else "foreign_object"
        hyp.hypothesis.score = 0.92
        det.results.append(hyp)
        arr.detections.append(det)
        return arr

    def _class_name(self, cls_id: int) -> str:
        if 0 <= cls_id < len(self.class_labels):
            return self.class_labels[cls_id]
        return str(cls_id)

    def _to_detection_array(self, result, header) -> Detection2DArray:
        arr = Detection2DArray()
        arr.header = header
        if result.boxes is None:
            return arr

        for box in result.boxes:
            cls_id = int(box.cls.item())
            conf = float(box.conf.item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            det = Detection2D()
            det.header = header
            det.bbox.center.x = (x1 + x2) / 2.0
            det.bbox.center.y = (y1 + y2) / 2.0
            det.bbox.size_x = x2 - x1
            det.bbox.size_y = y2 - y1

            hyp = ObjectHypothesisWithPose()
            hyp.hypothesis.class_id = self._class_name(cls_id)
            hyp.hypothesis.score = conf
            det.results.append(hyp)
            arr.detections.append(det)

        return arr

    def _build_summary(self, detections: Detection2DArray) -> str:
        if not detections.detections:
            return ""
        names = [d.results[0].hypothesis.class_id for d in detections.detections if d.results]
        return "detected: " + ", ".join(names)

    def _update_fps(self) -> None:
        self._frame_count += 1
        elapsed = time.monotonic() - self._fps_window_start
        if elapsed >= self.fps_log_interval:
            fps = self._frame_count / elapsed
            self.get_logger().info(f"Inference FPS: {fps:.1f}")
            self._frame_count = 0
            self._fps_window_start = time.monotonic()


def main() -> None:
    rclpy.init()
    node = PerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
