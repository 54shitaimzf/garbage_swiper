# 部署指南（对齐《对接指南与提交自查.md》）

## 路径规范（重要）

| 用途 | 宿主机（放文件） | 容器内（传给系统） |
|------|-----------------|-------------------|
| 模型 | `~/icar_models/` | `/root/models/` |
| 地图 | `~/icar_maps/` | `/root/maps/` |

---

## PC 训练

```powershell
cd D:\北交大两周项目\icar_vision
py run_all.py
```

---

## 拷到小车（只拷 2 样）

| 本地 | 小车宿主机 |
|------|-----------|
| `models/best.onnx` | `~/icar_models/best.onnx` |
| `scripts/build_tensorrt_jetson.sh` | `~/icar_models/build_tensorrt_jetson.sh` |

可选：把整个 `ros2_ws/src/icar_perception/` 拷到 `~/icar_ws/src/` 用于自测。

---

## 转 TensorRT（Docker 内）

```bash
d
mkdir -p ~/icar_models /root/models
cp ~/icar_models/best.onnx /root/models/
cp ~/icar_models/build_tensorrt_jetson.sh /root/models/
chmod +x /root/models/build_tensorrt_jetson.sh
cd /root/models
pip3 install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple
bash build_tensorrt_jetson.sh /root/models 640
cp yolo.engine ~/icar_models/yolo.engine
```

---

## 交给框架组

1. 确认 `~/icar_models/yolo.engine` 存在
2. 发送 `C_交付清单.md` 里的类别标签和 yaml 配置

---

## 自测

```bash
ros2 launch icar_perception perception.launch.py
ros2 topic echo /detections
```

相机话题固定 `/image_raw`（框架组已配置 remap）。
