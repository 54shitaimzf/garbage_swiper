# C 同学（李子龙）交付清单 — 感知模块

> 按《对接指南与提交自查.md》§3 整理，直接发给框架组（马展飞）。

---

## 一、你要交付的产物（2 样）

| 序号 | 交付物 | 格式 | 放置路径（宿主机） | 容器内路径 |
|------|--------|------|-------------------|------------|
| 1 | TensorRT 模型 | `yolo.engine` | `~/icar_models/yolo.engine` | `/root/models/yolo.engine` |
| 2 | 类别标签列表 | 见下方 | 发给框架组写入 yaml | — |

**类别标签（与训练 data.yaml 顺序一致）：**

```yaml
class_labels:
  - drink_white    # 0 白色水杯
  - drink_red      # 1 红色酸梅汤
  - drink_green    # 2 绿色雪碧
  - backpack       # 3 黑书包
  - tea_box        # 4 茶叶盒
```

---

## 二、交给框架组的配置字段（§3.5）

```yaml
perception_node:
  ros__parameters:
    use_sim_detection: false
    model_path: "/root/models/yolo.engine"
    confidence_threshold: 0.5
    image_topic: "/image_raw"
    detection_rate_hz: 10.0
    input_size: 640
    class_labels:
      - drink_white
      - drink_red
      - drink_green
      - backpack
      - tea_box
```

完整 yaml 文件位置：`icar_vision/ros2_ws/src/icar_perception/config/perception_params.yaml`

---

## 三、你怎么产出 yolo.engine

### PC 上（已完成）

```powershell
cd D:\北交大两周项目\icar_vision
py run_all.py
```

产出：`models/best.pt`、`models/best.onnx`

### 拷到小车

| Windows 文件 | 小车宿主机路径 |
|-------------|---------------|
| `models/best.onnx` | `~/icar_models/best.onnx` |
| `scripts/build_tensorrt_jetson.sh` | `~/icar_models/build_tensorrt_jetson.sh` |

⚠️ **注意路径变了**：是 `~/icar_models/`，不是 `~/models/`。

### 小车上转 engine（必须在 Orin 容器内）

```bash
d
mkdir -p /root/models
cp ~/icar_models/best.onnx /root/models/
cp ~/icar_models/build_tensorrt_jetson.sh /root/models/
chmod +x /root/models/build_tensorrt_jetson.sh
cd /root/models
pip3 install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple
bash build_tensorrt_jetson.sh /root/models 640
cp /root/models/yolo.engine ~/icar_models/yolo.engine
ls -lh ~/icar_models/yolo.engine
```

---

## 四、验收自查（§3.6）

- [ ] `yolo.engine` 在 `~/icar_models/`，容器内 `/root/models/` 能加载（无 `could not deserialize`）
- [ ] `/detections` 输出真实 `Detection2DArray`（非 sim）
- [ ] 相机话题 `/image_raw` 有图像（框架组已 remap，你不用再改）
- [ ] 车前置测试物，`mission` 状态能跳到 ALARM

---

## 五、你不需要做的事

- ❌ 不用自己改 `icar_bringup`（框架组嵌入配置）
- ❌ 不用重训模型（现有 5 类即可）
- ❌ 不用管 MQTT / APP / 地图（其他组员负责）

---

## 六、自测命令（模型就位后）

```bash
d
source ~/icar_ws/install/setup.bash   # 若框架组已集成 perception_node
ros2 topic echo /detections
# 或独立测：
ros2 launch icar_perception perception.launch.py use_sim_detection:=false
```

放演示物到相机前，应看到 `class_id: drink_red` 等字段。
