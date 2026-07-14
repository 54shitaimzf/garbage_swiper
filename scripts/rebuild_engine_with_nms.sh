#!/bin/bash
# 在 Jetson Orin 上：导出带 EfficientNMS 的 engine + 生成 model_manifest.json
# 用法: bash rebuild_engine_with_nms.sh ~/icar_models
set -euo pipefail

MODEL_DIR="${1:-$HOME/icar_models}"
cd "$MODEL_DIR"

if [ ! -f best.pt ]; then
  echo "ERROR: 需要 $MODEL_DIR/best.pt"
  exit 1
fi

echo "=== 1) 导出 TensorRT engine（带 NMS，对接组长 EfficientNMS）==="
pip3 install "numpy<1.24" ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple || true

python3 - <<'PY'
from ultralytics import YOLO
m = YOLO("best.pt")
# nms=True → TensorRT EfficientNMS 插件（count/boxes/scores/classes）
out = m.export(format="engine", imgsz=640, half=True, device=0, nms=True)
print("ENGINE:", out)
PY

# 统一交付名
if [ -f best.engine ]; then
  cp -f best.engine yolo.engine
elif [ -f best.engine ]; then
  true
fi

ls -lh best.engine yolo.engine 2>/dev/null || ls -lh *.engine

echo "=== 2) 生成 model_manifest.json ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/generate_model_manifest.py" ]; then
  GEN="$SCRIPT_DIR/generate_model_manifest.py"
elif [ -f generate_model_manifest.py ]; then
  GEN=./generate_model_manifest.py
else
  echo "请把 generate_model_manifest.py 拷到 $MODEL_DIR"
  exit 1
fi

python3 "$GEN" --engine best.engine --out model_manifest.json

echo "=== 3) 校验哈希 ==="
sha256sum best.engine
echo "DONE. 交付："
echo "  $MODEL_DIR/best.engine"
echo "  $MODEL_DIR/model_manifest.json"
echo "  $MODEL_DIR/validation/foreign-object.jpg  （需自备一张图并手标 expected_box_xyxy）"
