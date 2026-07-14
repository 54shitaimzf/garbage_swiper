#!/usr/bin/env bash
set -euo pipefail

ROOT="${ICAR_AUTONOMY_ROOT:-/home/jetson/garbage_swiper_v2}"
cd "$ROOT"
export ICAR_MAP_ROOT="${ICAR_MAP_ROOT:-/home/jetson/icar_maps}"
export AUTONOMY_MODE="${AUTONOMY_MODE:-mock}"
export AUTONOMY_PORT="${AUTONOMY_PORT:-8082}"

exec python3 -m autonomy.server --host 0.0.0.0 --port "$AUTONOMY_PORT" --mode "$AUTONOMY_MODE"
