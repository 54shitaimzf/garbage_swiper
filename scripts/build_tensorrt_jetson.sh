#!/bin/bash
# Run ON Jetson Orin Nano only (not Windows).
# Produces yolo.engine per team interface: /root/models/yolo.engine
set -euo pipefail

MODEL_DIR="${1:-/root/models}"
IMGSZ="${2:-640}"
ONNX="${MODEL_DIR}/best.onnx"
ENGINE="${MODEL_DIR}/yolo.engine"
TRTEXEC="/usr/src/tensorrt/bin/trtexec"

mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

if [ ! -f "$ONNX" ]; then
  if [ -f best.pt ]; then
    echo "=== Export ONNX from best.pt ==="
    pip3 install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple || true
    python3 - <<PY
from ultralytics import YOLO
m = YOLO("best.pt")
onnx = m.export(format="onnx", imgsz=${IMGSZ}, simplify=True, opset=12)
print("ONNX:", onnx)
PY
  else
    echo "ERROR: missing $ONNX (and no best.pt to export from)"
    exit 1
  fi
fi

echo "=== Build TensorRT engine (FP16) ==="
if [ -x "$TRTEXEC" ]; then
  "$TRTEXEC" --onnx="$ONNX" --saveEngine="$ENGINE" --fp16 --workspaceSize=1024
elif command -v trtexec >/dev/null 2>&1; then
  trtexec --onnx="$ONNX" --saveEngine="$ENGINE" --fp16 --workspaceSize=1024
else
  echo "trtexec not found, fallback to ultralytics engine export"
  pip3 install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple || true
  python3 - <<PY
from ultralytics import YOLO
m = YOLO("best.pt")
engine = m.export(format="engine", imgsz=${IMGSZ}, half=True, device=0)
print("ENGINE:", engine)
PY
  if [ -f best.engine ] && [ ! -f "$ENGINE" ]; then
    cp best.engine "$ENGINE"
  fi
fi

if [ -f "$ENGINE" ]; then
  ls -lh "$ENGINE"
  echo "SUCCESS: TensorRT engine ready at $ENGINE"
else
  echo "ERROR: yolo.engine not created"
  exit 1
fi
