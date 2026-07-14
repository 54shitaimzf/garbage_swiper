#!/usr/bin/env python3
"""Evaluate model on all raw class folders; save annotated images."""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO

CLASS_DIRS = ["drink_white", "drink_red", "drink_green", "backpack", "tea_box", "multi"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "best.pt",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "dataset" / "raw",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "eval_results",
    )
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"Model not found: {args.model}")

    args.out.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(args.model))

    summary_lines = []
    for name in CLASS_DIRS:
        folder = args.raw / name
        if not folder.exists():
            continue
        images = list(folder.glob("*.*"))
        if not images:
            summary_lines.append(f"{name}: 0 images")
            continue
        save_dir = args.out / name
        save_dir.mkdir(parents=True, exist_ok=True)
        results = model.predict(
            source=str(folder),
            conf=args.conf,
            imgsz=args.imgsz,
            save=True,
            project=str(args.out),
            name=name,
            exist_ok=True,
        )
        hits = sum(1 for r in results if r.boxes is not None and len(r.boxes) > 0)
        summary_lines.append(f"{name}: {hits}/{len(results)} detected")

    report = args.out / "eval_summary.txt"
    report.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print("\n".join(summary_lines))
    print(f"\nReport: {report}")
    print(f"Images: {args.out}")


if __name__ == "__main__":
    main()
