#!/usr/bin/env python3
"""One-click: label -> augment -> train -> export ONNX -> local eval."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str]) -> None:
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT.parent)


def main() -> None:
    py = sys.executable
    run([py, str(SCRIPTS / "auto_label.py")])
    run([py, str(SCRIPTS / "augment_dataset.py"), "--copies", "12"])
    run([
        py, str(SCRIPTS / "train.py"),
        "--model", "yolov8s.pt",
        "--epochs", "80",
        "--batch", "8",
        "--imgsz", "640",
        "--device", "0",
    ])
    run([py, str(SCRIPTS / "export_onnx.py"), "--imgsz", "640"])
    run([py, str(SCRIPTS / "eval_all.py"), "--imgsz", "640"])
    print("\nDone.")
    print("  PC:  icar_vision/models/best.pt + best.onnx")
    print("  Jetson: copy to /root/models/, then bash build_tensorrt_jetson.sh")
    print("  Output: /root/models/yolo.engine")


if __name__ == "__main__":
    main()
