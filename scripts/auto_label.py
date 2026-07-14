#!/usr/bin/env python3
"""Auto-generate YOLO labels from raw photos using contour/color detection."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

# class folder name -> class id (must match data.yaml)
CLASS_MAP = {
    "drink_white": 0,
    "drink_red": 1,
    "drink_green": 2,
    "backpack": 3,
    "tea_box": 4,
}

# fallback relative box when contour detection fails: (cx, cy, w, h) in 0~1
FALLBACK_BOX = {
    "drink_white": (0.5, 0.52, 0.28, 0.55),
    "drink_red": (0.5, 0.52, 0.26, 0.55),
    "drink_green": (0.5, 0.52, 0.26, 0.55),
    "backpack": (0.5, 0.50, 0.55, 0.65),
    "tea_box": (0.5, 0.55, 0.42, 0.38),
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def imread_unicode(path: Path) -> np.ndarray | None:
    """Read image with Unicode path support on Windows."""
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


def detect_box(image: np.ndarray, class_name: str) -> tuple[float, float, float, float]:
    """Return YOLO box (cx, cy, w, h) normalized to 0~1."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        best = None
        best_score = 0.0
        cx_img, cy_img = w / 2, h / 2
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            if area < w * h * 0.02:
                continue
            mx, my = x + bw / 2, y + bh / 2
            dist = np.hypot(mx - cx_img, my - cy_img) / max(w, h)
            score = area * (1.0 - dist)
            if score > best_score:
                best_score = score
                best = (x, y, bw, bh)
        if best is not None:
            x, y, bw, bh = best
            pad = 0.08
            x = max(0, int(x - bw * pad))
            y = max(0, int(y - bh * pad))
            bw = min(w - x, int(bw * (1 + 2 * pad)))
            bh = min(h - y, int(bh * (1 + 2 * pad)))
            return (x + bw / 2) / w, (y + bh / 2) / h, bw / w, bh / h

    return FALLBACK_BOX[class_name]


def _mask_boxes(mask: np.ndarray, img_w: int, img_h: int, min_area_ratio: float = 0.01):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw * bh < img_w * img_h * min_area_ratio:
            continue
        boxes.append((x, y, bw, bh))
    return boxes


def _to_yolo(x, y, bw, bh, img_w, img_h):
    return (x + bw / 2) / img_w, (y + bh / 2) / img_h, bw / img_w, bh / img_h


def _iou(a, b) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def detect_multi(image: np.ndarray) -> list[tuple[int, float, float, float, float]]:
    """Detect multiple demo objects in one frame using color heuristics."""
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    detections: list[tuple[int, tuple[int, int, int, int]]] = []

    # red -> drink_red
    red1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([160, 80, 80]), np.array([180, 255, 255]))
    for box in _mask_boxes(red1 | red2, w, h, 0.008):
        detections.append((1, box))

    # green -> drink_green
    green = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([85, 255, 255]))
    for box in _mask_boxes(green, w, h, 0.008):
        detections.append((2, box))

    # white -> drink_white
    white = cv2.inRange(hsv, np.array([0, 0, 170]), np.array([180, 60, 255]))
    for box in _mask_boxes(white, w, h, 0.008):
        detections.append((0, box))

    # dark large -> backpack
    dark = cv2.inRange(gray, 0, 70)
    for box in _mask_boxes(dark, w, h, 0.06):
        detections.append((3, box))

    # brown/gold box -> tea_box
    tea = cv2.inRange(hsv, np.array([8, 40, 40]), np.array([35, 255, 220]))
    for box in _mask_boxes(tea, w, h, 0.02):
        x, y, bw, bh = box
        aspect = bw / max(bh, 1)
        if 0.5 < aspect < 2.5:
            detections.append((4, box))

    # NMS per class
    final: list[tuple[int, float, float, float, float]] = []
    for class_id in range(5):
        cls_boxes = [b for cid, b in detections if cid == class_id]
        kept = []
        for box in sorted(cls_boxes, key=lambda b: b[2] * b[3], reverse=True):
            if all(_iou(box, k) < 0.35 for k in kept):
                kept.append(box)
        for box in kept[:2]:  # at most 2 per class in one image
            final.append((class_id, *_to_yolo(*box, w, h)))

    return final


def process_single_class(raw_dir: Path, out_img_dir: Path, out_lbl_dir: Path) -> int:
    total = 0
    for class_name, class_id in CLASS_MAP.items():
        class_dir = raw_dir / class_name
        if not class_dir.exists():
            print(f"[WARN] missing folder: {class_dir}")
            continue
        files = sorted(p for p in class_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        if not files:
            print(f"[WARN] no images in {class_dir}")
            continue

        for img_path in files:
            img = imread_unicode(img_path)
            if img is None:
                print(f"[SKIP] unreadable: {img_path}")
                continue
            cx, cy, bw, bh = detect_box(img, class_name)
            stem = f"{class_name}_{img_path.stem}"
            out_img = out_img_dir / f"{stem}{img_path.suffix.lower()}"
            out_lbl = out_lbl_dir / f"{stem}.txt"
            imwrite_unicode(out_img, img)
            out_lbl.write_text(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8")
            total += 1
            print(f"[OK] {img_path.name} -> {out_lbl.name}")
    return total


def process_multi(raw_dir: Path, out_img_dir: Path, out_lbl_dir: Path) -> int:
    multi_dir = raw_dir / "multi"
    if not multi_dir.exists():
        print("[INFO] no multi/ folder, skip multi-object labeling")
        return 0

    total = 0
    files = sorted(p for p in multi_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    for img_path in files:
        img = imread_unicode(img_path)
        if img is None:
            print(f"[SKIP] unreadable: {img_path}")
            continue
        rows = detect_multi(img)
        if not rows:
            print(f"[WARN] no objects detected in {img_path.name}, skipped")
            continue
        stem = f"multi_{img_path.stem}"
        out_img = out_img_dir / f"{stem}{img_path.suffix.lower()}"
        out_lbl = out_lbl_dir / f"{stem}.txt"
        cv2.imwrite(str(out_img), img)
        lines = [f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}" for cid, cx, cy, bw, bh in rows]
        out_lbl.write_text("\n".join(lines) + "\n", encoding="utf-8")
        total += 1
        names = [list(CLASS_MAP.keys())[cid] for cid, *_ in rows]
        print(f"[OK] {img_path.name} -> {out_lbl.name} ({', '.join(names)})")
    return total


def process_raw(raw_dir: Path, out_dir: Path) -> None:
    images_out = out_dir / "images" / "raw_labeled"
    labels_out = out_dir / "labels" / "raw_labeled"
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    n1 = process_single_class(raw_dir, images_out, labels_out)
    n2 = process_multi(raw_dir, images_out, labels_out)
    print(f"\nDone. Labeled {n1 + n2} images (single: {n1}, multi: {n2}).")
    print(f"Images: {images_out}")
    print(f"Labels: {labels_out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto label raw dataset for YOLO")
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "dataset" / "raw",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "dataset" / "yolo",
    )
    args = parser.parse_args()
    process_raw(args.raw, args.out)


if __name__ == "__main__":
    main()
