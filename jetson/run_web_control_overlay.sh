#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONUNBUFFERED=1
export WEB_CONTROL_PORT="${WEB_CONTROL_PORT:-8081}"
export ROBOT_TCP_HOST="${ROBOT_TCP_HOST:-10.71.253.19}"
export ROBOT_TCP_PORT="${ROBOT_TCP_PORT:-6000}"
export CAMERA_SOURCE="${CAMERA_SOURCE:-/dev/video0}"
export CAMERA_FPS="${CAMERA_FPS:-5}"
export YOLO_MODEL="${YOLO_MODEL:-/home/jetson/icar_models/best.engine}"
export YOLO_CONF="${YOLO_CONF:-0.35}"
export YOLO_INTERVAL="${YOLO_INTERVAL:-2}"
exec python3 "$ROOT/jetson/web_control_gateway_overlay.py"
