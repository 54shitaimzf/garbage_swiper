#!/usr/bin/env python3
"""Export best.pt to ONNX (copy to Jetson, then build TensorRT engine there)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "best.pt",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models",
    )
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"Model not found: {args.model}")

    model = YOLO(str(args.model))
    exported = model.export(format="onnx", imgsz=args.imgsz, simplify=True, opset=12)
    src = Path(exported).resolve()
    dst = (args.out / "best.onnx").resolve()
    if src != dst:
        shutil.copy2(src, dst)
    print(f"ONNX saved: {dst}")
    print("Copy best.pt + best.onnx to Jetson /root/models/, then:")
    print("  bash build_tensorrt_jetson.sh /root/models 640")
    print("  -> produces /root/models/yolo.engine")


if __name__ == "__main__":
    main()
