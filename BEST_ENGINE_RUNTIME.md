# 当前 AI 运行入口

统一使用：

```bash
python3 /home/jetson/garbage_swiper_v2/edge/run_best_engine.py \
  --source /dev/video0 \
  --output-dir /home/jetson/garbage_swiper_v2/artifacts \
  --frames 1
```

模型固定为 `/home/jetson/icar_models/best.engine`。`/dev/video0` 是当前 Astra 彩色 V4L2 节点；`/dev/camera_depth -> /dev/video1` 是深度节点，不能直接按普通彩色 V4L2 帧交给 YOLO。
