#!/usr/bin/env python3
"""Minimal Jetson inference runner for the already-provisioned icar_models engine.

This intentionally stays outside ROS2 for the first acceptance run: it exercises
the vendor model and camera device without competing for the ROS camera node.
"""
import argparse
import json
import os
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/home/jetson/icar_models/yolo.engine")
    parser.add_argument("--source", default="/home/jetson/icar_models/test.jpg")
    parser.add_argument("--output-dir", default="/home/jetson/garbage_swiper/artifacts")
    parser.add_argument("--frames", type=int, default=1)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    return parser.parse_args()


def frame_source(source, width, height):
    if source.isdigit():
        source = int(source)
    if isinstance(source, str) and source.startswith("/dev/"):
        source = cv2.VideoCapture(source, cv2.CAP_V4L2)
    elif isinstance(source, int):
        source = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not hasattr(source, "read"):
        image = cv2.imread(str(source))
        if image is None:
            raise FileNotFoundError(source)
        while True:
            yield image.copy()
    else:
        source.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        source.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        try:
            while True:
                ok, image = source.read()
                if not ok:
                    raise RuntimeError("camera read failed")
                yield image
        finally:
            source.release()


def main():
    args = parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model = YOLO(args.model)
    names = model.names
    detections = []
    source = str(args.source)
    for index, image in enumerate(frame_source(source, args.width, args.height)):
        result = model.predict(image, conf=args.conf, verbose=False)[0]
        annotated = result.plot()
        image_path = out / ("yolo_result.jpg" if args.frames == 1 else f"yolo_{index:04d}.jpg")
        cv2.imwrite(str(image_path), annotated)
        for box in result.boxes:
            cls_id = int(box.cls.item())
            detections.append({
                "timestamp": time.time(),
                "class_id": cls_id,
                "class_name": names.get(cls_id, str(cls_id)) if isinstance(names, dict) else names[cls_id],
                "confidence": round(float(box.conf.item()), 4),
                "bbox_xyxy": [round(float(v), 2) for v in box.xyxy[0].tolist()],
                "source": source,
            })
        print(json.dumps({"frame": index, "detections": detections[-20:], "image": str(image_path)}, ensure_ascii=False))
        if index + 1 >= args.frames:
            break
    (out / "detections.json").write_text(json.dumps(detections, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "frames": min(args.frames, index + 1), "detections": len(detections), "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
