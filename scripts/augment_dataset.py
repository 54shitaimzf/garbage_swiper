#!/usr/bin/env python3
"""Augment labeled images for fast demo-grade overfitting."""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import albumentations as A
import cv2
import numpy as np
import yaml

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def imread_unicode(path: Path) -> np.ndarray | None:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_unicode(path: Path, image: np.ndarray) -> bool:
    ext = path.suffix.lower() or ".jpg"
    ok, buf = cv2.imencode(ext, image)
    if not ok:
        return False
    buf.tofile(str(path))
    return True


def read_yolo_labels(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    rows = []
    for line in label_path.read_text(encoding="utf-8").strip().splitlines():
        cid, cx, cy, w, h = line.split()
        rows.append((int(cid), float(cx), float(cy), float(w), float(h)))
    return rows


def write_yolo_labels(label_path: Path, rows: list[tuple[int, float, float, float, float]]) -> None:
    lines = [f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cid, cx, cy, w, h in rows]
    label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def yolo_to_albu(rows: list[tuple[int, float, float, float, float]], w: int, h: int):
    bboxes = []
    class_labels = []
    for cid, cx, cy, bw, bh in rows:
        x_min = max(0.0, (cx - bw / 2) * w)
        y_min = max(0.0, (cy - bh / 2) * h)
        x_max = min(float(w), (cx + bw / 2) * w)
        y_max = min(float(h), (cy + bh / 2) * h)
        bboxes.append([x_min, y_min, x_max, y_max])
        class_labels.append(cid)
    return bboxes, class_labels


def albu_to_yolo(bboxes, class_labels, w: int, h: int):
    rows = []
    for bbox, cid in zip(bboxes, class_labels):
        x_min, y_min, x_max, y_max = bbox
        cx = ((x_min + x_max) / 2) / w
        cy = ((y_min + y_max) / 2) / h
        bw = (x_max - x_min) / w
        bh = (y_max - y_min) / h
        rows.append((int(cid), cx, cy, bw, bh))
    return rows


def build_pipeline() -> A.Compose:
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.Rotate(limit=20, border_mode=cv2.BORDER_REFLECT_101, p=0.7),
            A.RandomBrightnessContrast(brightness_limit=0.25, contrast_limit=0.25, p=0.7),
            A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=25, val_shift_limit=25, p=0.5),
            A.GaussNoise(p=0.3),
            A.Blur(blur_limit=3, p=0.2),
            A.RandomScale(scale_limit=0.15, p=0.5),
        ],
        bbox_params=A.BboxParams(format="pascal_voc", label_fields=["class_labels"], min_visibility=0.3),
    )


def split_and_augment(
    src_images: Path,
    src_labels: Path,
    dst_root: Path,
    copies_per_image: int,
    val_ratio: float,
) -> None:
    train_img = dst_root / "images" / "train"
    val_img = dst_root / "images" / "val"
    train_lbl = dst_root / "labels" / "train"
    val_lbl = dst_root / "labels" / "val"
    for p in [train_img, val_img, train_lbl, val_lbl]:
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)

    pairs = []
    for img_path in sorted(src_images.iterdir()):
        if img_path.suffix.lower() not in IMAGE_EXTS:
            continue
        lbl_path = src_labels / f"{img_path.stem}.txt"
        if lbl_path.exists():
            pairs.append((img_path, lbl_path))

    random.seed(42)
    random.shuffle(pairs)
    val_count = max(1, int(len(pairs) * val_ratio))
    val_pairs = pairs[:val_count]
    train_pairs = pairs[val_count:]

    pipeline = build_pipeline()

    def copy_pair(img_path: Path, lbl_path: Path, out_img_dir: Path, out_lbl_dir: Path, suffix: str = "") -> None:
        img = imread_unicode(img_path)
        if img is None:
            return
        h, w = img.shape[:2]
        rows = read_yolo_labels(lbl_path)
        out_name = f"{img_path.stem}{suffix}{img_path.suffix.lower()}"
        imwrite_unicode(out_img_dir / out_name, img)
        shutil.copy2(lbl_path, out_lbl_dir / f"{img_path.stem}{suffix}.txt")

    def augment_pair(img_path: Path, lbl_path: Path, out_img_dir: Path, out_lbl_dir: Path, idx: int) -> None:
        img = imread_unicode(img_path)
        if img is None:
            return
        h, w = img.shape[:2]
        rows = read_yolo_labels(lbl_path)
        bboxes, class_labels = yolo_to_albu(rows, w, h)
        for attempt in range(5):
            transformed = pipeline(image=img, bboxes=bboxes, class_labels=class_labels)
            if transformed["bboxes"]:
                new_rows = albu_to_yolo(transformed["bboxes"], transformed["class_labels"], w, h)
                out_name = f"{img_path.stem}_aug{idx}{img_path.suffix.lower()}"
                imwrite_unicode(out_img_dir / out_name, transformed["image"])
                write_yolo_labels(out_lbl_dir / f"{img_path.stem}_aug{idx}.txt", new_rows)
                return

    for img_path, lbl_path in val_pairs:
        copy_pair(img_path, lbl_path, val_img, val_lbl, "_val")

    for img_path, lbl_path in train_pairs:
        copy_pair(img_path, lbl_path, train_img, train_lbl, "_orig")
        for i in range(copies_per_image):
            augment_pair(img_path, lbl_path, train_img, train_lbl, i)

    print(f"Train pairs(base): {len(train_pairs)}, augmented copies each: {copies_per_image}")
    print(f"Val pairs: {len(val_pairs)}")
    print(f"Train images: {len(list(train_img.iterdir()))}")
    print(f"Val images: {len(list(val_img.iterdir()))}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "dataset" / "yolo",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "dataset" / "yolo",
    )
    parser.add_argument("--copies", type=int, default=8, help="augmented copies per training image")
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    src_images = args.src / "images" / "raw_labeled"
    src_labels = args.src / "labels" / "raw_labeled"
    if not src_images.exists():
        raise SystemExit(f"Run auto_label.py first. Missing {src_images}")

    split_and_augment(src_images, src_labels, args.out, args.copies, args.val_ratio)

    data_yaml = Path(__file__).resolve().parents[2] / "dataset" / "data.yaml"
    cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    cfg["path"] = str(args.out.resolve())
    cfg["train"] = "images/train"
    cfg["val"] = "images/val"
    (args.out / "data.yaml").write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Wrote {args.out / 'data.yaml'}")


if __name__ == "__main__":
    main()
