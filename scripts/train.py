#!/usr/bin/env python3
"""Train YOLOv8 on demo dataset (upgraded defaults: yolov8s, 640px)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "dataset" / "yolo" / "data.yaml",
    )
    parser.add_argument("--model", type=str, default="yolov8s.pt", help="yolov8n.pt or yolov8s.pt")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", type=str, default="0")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models",
    )
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"Dataset not found: {args.data}\nRun auto_label.py and augment_dataset.py first.")

    args.out.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)
    results = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=args.patience,
        project=str(args.out / "runs"),
        name="foreign_objects_v2",
        exist_ok=True,
        pretrained=True,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        mosaic=1.0,
        mixup=0.1,
        copy_paste=0.1,
        flipud=0.0,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        workers=4,
        close_mosaic=10,
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    final = args.out / "best.pt"
    shutil.copy2(best, final)
    print(f"\nTraining done.")
    print(f"Best weights: {final}")
    print("Next: py scripts/export_onnx.py && py scripts/eval_all.py")


if __name__ == "__main__":
    main()
