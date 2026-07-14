#!/usr/bin/env python3
"""在 Jetson 上生成 model_manifest.json（对接组长 EfficientNMS 契约）。

用法（在小车 ~/icar_models 目录）：
  python3 generate_model_manifest.py --engine best.engine
  python3 generate_model_manifest.py --engine yolo.engine --out model_manifest.json

类别顺序来自训练 data.yaml，不会猜测。
binding 名称从 engine 实际读取，不会照抄示例。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# 来自训练时 dataset/yolo/data.yaml，顺序不可改
LABELS = [
    "drink_white",
    "drink_red",
    "drink_green",
    "backpack",
    "tea_box",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_engine(engine_path: Path):
    import tensorrt as trt

    logger = trt.Logger(trt.Logger.ERROR)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(engine_path.read_bytes())
    if engine is None:
        raise SystemExit(f"无法反序列化 engine: {engine_path}")

    bindings = []
    for i in range(engine.num_bindings):
        name = engine.get_binding_name(i)
        is_input = engine.binding_is_input(i)
        shape = tuple(engine.get_binding_shape(i))
        dtype = str(trt.nptype(engine.get_binding_dtype(i)).__name__)
        bindings.append(
            {
                "index": i,
                "name": name,
                "io": "INPUT" if is_input else "OUTPUT",
                "shape": list(shape),
                "dtype": dtype,
            }
        )
        print(i, "INPUT" if is_input else "OUTPUT", name, shape, dtype)
    return bindings


def pick_input(bindings):
    inputs = [b for b in bindings if b["io"] == "INPUT"]
    if not inputs:
        raise SystemExit("engine 没有 INPUT binding")
    # 优先 images，否则取第一个输入
    for b in inputs:
        if b["name"].lower() in ("images", "input", "input_0"):
            return b
    return inputs[0]


def pick_efficient_nms_outputs(bindings):
    outs = {b["name"]: b for b in bindings if b["io"] == "OUTPUT"}
    names_lower = {n.lower(): n for n in outs}

    def find(*cands):
        for c in cands:
            if c in outs:
                return c
            if c.lower() in names_lower:
                return names_lower[c.lower()]
        return None

    count = find("num_dets", "count", "num_detections", "detection_count")
    boxes = find("det_boxes", "boxes", "detection_boxes")
    scores = find("det_scores", "scores", "detection_scores")
    classes = find("det_classes", "classes", "detection_classes")

    if not all([count, boxes, scores, classes]):
        print("\n[WARNING] 未找到完整 EfficientNMS 四元组输出。")
        print("当前 OUTPUT bindings:", list(outs.keys()))
        print(
            "组长要求 count/boxes/scores/classes。"
            "请用 Ultralytics 重新导出带 NMS 的 engine：\n"
            '  yolo export model=best.pt format=engine half=True imgsz=640 device=0 nms=True\n'
            "然后重新运行本脚本。"
        )
        return None

    return {"count": count, "boxes": boxes, "scores": scores, "classes": classes}


def input_wh(shape):
    # NCHW: (N,C,H,W) or dynamic
    if len(shape) == 4:
        h, w = shape[2], shape[3]
        if h > 0 and w > 0:
            return int(w), int(h)
    return 640, 640


def dtype_name(numpy_name: str) -> str:
    mapping = {
        "float32": "float32",
        "float16": "float16",
        "int32": "int32",
        "int64": "int64",
        "bool": "bool",
    }
    return mapping.get(numpy_name, numpy_name)


def build_manifest(engine_path: Path, bindings, outputs, validation_image: Path | None):
    inp = pick_input(bindings)
    w, h = input_wh(inp["shape"])
    dig = sha256_file(engine_path)

    manifest = {
        "schema_version": 1,
        "engine_file": engine_path.name,
        "engine_sha256": dig,
        "input": {
            "binding": inp["name"],
            "layout": "NCHW",
            "dtype": dtype_name(inp["dtype"]),
            "width": w,
            "height": h,
            # Ultralytics 训练/导出默认 RGB + letterbox；若组长 C++ 只支持 stretch/BGR，需与 A 确认
            "color_order": "RGB",
            "resize_mode": "letterbox",
        },
        "outputs": outputs
        or {
            "count": "FIXME_run_script_after_nms_export",
            "boxes": "FIXME_run_script_after_nms_export",
            "scores": "FIXME_run_script_after_nms_export",
            "classes": "FIXME_run_script_after_nms_export",
        },
        "decoder": {
            "format": "efficient_nms",
            "box_format": "xyxy",
            "boxes_normalized": False,
        },
        "labels": LABELS,
        "confidence_threshold": 0.5,
    }

    if validation_image and validation_image.exists():
        manifest["validation"] = {
            "image_file": f"validation/{validation_image.name}",
            "image_sha256": sha256_file(validation_image),
            "expected_class": LABELS[1],  # drink_red 演示最稳，可改
            "minimum_score": 0.5,
            "expected_box_xyxy": [0, 0, 0, 0],  # 必须人工改成真实框
            "minimum_iou": 0.5,
        }
        print(
            f"\n[NOTE] validation.expected_box_xyxy 仍是占位 [0,0,0,0]，"
            f"请对 {validation_image} 人工标框后手工改 JSON。"
        )
    else:
        manifest["validation"] = {
            "image_file": "validation/foreign-object.jpg",
            "image_sha256": "待填：sha256sum validation/foreign-object.jpg",
            "expected_class": "drink_red",
            "minimum_score": 0.5,
            "expected_box_xyxy": [100, 80, 420, 360],
            "minimum_iou": 0.5,
            "_note": "请换成真实测试图路径、哈希与人工标注框",
        }

    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, default=Path("best.engine"))
    parser.add_argument("--out", type=Path, default=Path("model_manifest.json"))
    parser.add_argument("--validation-image", type=Path, default=None)
    args = parser.parse_args()

    if not args.engine.exists():
        raise SystemExit(f"找不到 engine: {args.engine.resolve()}")

    print(f"=== Inspect {args.engine.resolve()} ===")
    bindings = inspect_engine(args.engine)
    outputs = pick_efficient_nms_outputs(bindings)
    manifest = build_manifest(args.engine, bindings, outputs, args.validation_image)

    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {args.out.resolve()}")
    if outputs is None:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
