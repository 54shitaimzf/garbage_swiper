#!/usr/bin/env python3
"""Export trained model to ONNX for deployment."""

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
    parser.add_argument("--imgsz", type=int, default=416)
    args = parser.parse_args()

    model = YOLO(str(args.model))
    exported = model.export(format="onnx", imgsz=args.imgsz, simplify=True)
    exported_path = Path(exported)
    target = args.out / "best.onnx"
    shutil.copy2(exported_path, target)
    print(f"ONNX exported to: {target}")


if __name__ == "__main__":
    main()
