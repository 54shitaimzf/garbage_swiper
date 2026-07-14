#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONUNBUFFERED=1
export WEB_CONTROL_PORT="${WEB_CONTROL_PORT:-8080}"
export ROBOT_TCP_HOST="${ROBOT_TCP_HOST:-127.0.0.1}"
export ROBOT_TCP_PORT="${ROBOT_TCP_PORT:-6000}"
exec python3 "$ROOT/jetson/web_control_gateway.py"
