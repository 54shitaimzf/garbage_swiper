#!/usr/bin/env python3
"""Quick local test after training."""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "best.pt",
    )
    parser.add_argument("--source", type=str, required=True, help="image file or folder")
    parser.add_argument("--conf", type=float, default=0.35)
    args = parser.parse_args()

    model = YOLO(str(args.model))
    results = model.predict(source=args.source, conf=args.conf, save=True, imgsz=416)
    print(f"Saved predictions to: {results[0].save_dir}")


if __name__ == "__main__":
    main()
