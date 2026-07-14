# 李子龙 YOLO 异物检测工程代码说明（README）

> 学号：23301006  
> 角色：智能巡检小车 — AI 视觉 / YOLO 训练 / TensorRT 边缘部署  
> 检测类别：`drink_white`、`drink_red`、`drink_green`、`backpack`、`tea_box`

本仓库为 C 同学（李子龙）负责的**全部项目代码**，覆盖：数据采集后的自动标注 → 数据增强 → YOLOv8 训练 → ONNX/TensorRT 导出 → ROS2 感知节点与独立避障演示 → 交付辅助脚本。

---

## 1. 工程总览

```text
icar_vision/
├── README.md                          # 本文件：代码功能详解
├── requirements.txt                   # PC 训练依赖
├── run_all.py                         # 一键流水线入口
├── scripts/                           # PC / Jetson 工具脚本
│   ├── auto_label.py                  # 自动生成 YOLO 标签
│   ├── augment_dataset.py             # 数据增强
│   ├── train.py                       # YOLOv8 训练
│   ├── export_onnx.py                 # 导出 ONNX
│   ├── export_model.py                # 模型导出辅助
│   ├── eval_all.py                    # 本地批量评测
│   ├── test_inference.py              # 单路径推理测试
│   ├── build_tensorrt_jetson.sh       # Jetson 上转 .engine
│   ├── rebuild_engine_with_nms.sh     # 带 EfficientNMS 重导引擎
│   └── generate_model_manifest.py     # 生成 model_manifest.json
├── ros2_ws/src/icar_perception/       # ROS2 Foxy 感知功能包
│   ├── icar_perception/
│   │   ├── perception_node.py         # 检测节点（发布 /detections）
│   │   └── foreign_object_avoidance.py# 独立演示：告警 + 停车
│   ├── launch/
│   │   ├── perception.launch.py       # 组内联调（仅检测）
│   │   └── vision_demo.launch.py      # 检测 + 本地避障
│   ├── config/perception_params.yaml  # 给 bringup 嵌入的参数
│   ├── package.xml / setup.py
│   └── resource/
├── models/                            # 训练产物目录（见文末；大文件未必打进代码包）
└── 交付相关说明文档（DEPLOY.md 等）
```

**与组内系统关系：**

| 产物/接口 | 说明 |
|-----------|------|
| `best.pt` / `best.onnx` | PC 训练与中间格式 |
| `best.engine` / `yolo.engine` | Jetson TensorRT 引擎，放 `~/icar_models/` |
| `/detections` | `vision_msgs/Detection2DArray`，供 `icar_mission` 报警 |
| `/image_raw` | 相机输入（框架组 remap 后） |

---

## 2. PC 端脚本功能详解（`scripts/` + `run_all.py`）

### 2.1 `run_all.py` — 一键流水线

按顺序调用：

1. `auto_label.py` — 自动标注  
2. `augment_dataset.py --copies 12` — 增强约 12 倍  
3. `train.py` — YOLOv8s，80 epoch，640 输入，GPU  
4. `export_onnx.py` — 导出 `models/best.onnx`  
5. `eval_all.py` — 对原始类别文件夹做本地检出统计  

工作目录约定：脚本在 `icar_vision/` 下，数据集默认在上一级 `dataset/`。

**用法：**

```powershell
cd icar_vision
pip install -r requirements.txt
py run_all.py
```

---

### 2.2 `auto_label.py` — 自动生成 YOLO 标签

**功能：**

- 扫描 `dataset/raw/<类别名>/` 下图片（支持中文路径读写）  
- 用轮廓/边缘等方式估计目标框，失败则用按类别预设的 fallback 框  
- 写出 YOLO 格式 `.txt`：`class_id cx cy w h`（归一化）  
- 类别映射与 `data.yaml` 一致：

| id | 文件夹名 |
|----|----------|
| 0 | drink_white |
| 1 | drink_red |
| 2 | drink_green |
| 3 | backpack |
| 4 | tea_box |
| — | multi（多目标同框，特殊处理） |

**解决的问题：** 微信导出图片含中文文件名时，OpenCV 直接 `imread` 失败，本脚本用 `np.fromfile` + `imdecode` 兼容。

---

### 2.3 `augment_dataset.py` — 数据增强

**功能：**

- 读取已标注图片，用 Albumentations 做翻转、亮度、模糊、尺度等增强  
- 按 `--copies` 份数扩增，同步变换 YOLO 框  
- 输出到 `dataset/yolo/images/{train,val}` 与 `labels/{train,val}`，并维护 `data.yaml`

用于在样本不多时拉开训练集规模，便于 YOLOv8 收敛。

---

### 2.4 `train.py` — YOLOv8 训练

**功能：**

- 调用 Ultralytics API 训练（默认 `yolov8s.pt`，可改 `yolov8n`）  
- 参数：`epochs`、`imgsz`、`batch`、`device`、`patience` 等  
- 训练日志写到 `models/runs/foreign_objects_v2/`  
- 将最优权重复制为 `models/best.pt`

**典型命令：**

```powershell
py scripts/train.py --model yolov8s.pt --epochs 80 --batch 8 --imgsz 640 --device 0
```

---

### 2.5 `export_onnx.py` / `export_model.py` — 模型导出

**`export_onnx.py`：**

- 加载 `models/best.pt`  
- 导出 ONNX（opset 12、simplify），保存为 `models/best.onnx`  
- 若导出路径与目标路径相同则避免 `SameFileError`  

**用途：** 将 `best.onnx` 拷到 Jetson，再用 `trtexec` / Ultralytics 转 TensorRT。

---

### 2.6 `eval_all.py` — 本地批量评测

**功能：**

- 对 `dataset/raw` 下各类别图片跑检测  
- 统计每类检出张数，生成摘要与可视化到 `models/eval_results/`  
- 用于训练后快速看「哪一类还漏检」

---

### 2.7 `test_inference.py` — 单路径推理

**功能：**

- 指定 `--source` 为单图/文件夹，加载 `best.pt` 推理并保存带框结果  
- 便于演示前快速抽查某一类实物照片

---

### 2.8 `build_tensorrt_jetson.sh` — Jetson 上构建 `.engine`

**功能（须在 Orin 上执行）：**

1. 若无 ONNX，可从 `best.pt` 先导出  
2. 优先使用 `/usr/src/tensorrt/bin/trtexec --fp16`  
3. 若无 `trtexec`，回退到 Ultralytics `format=engine`  
4. 产出约定名：`yolo.engine`（及兼容命名）

**用法：**

```bash
bash build_tensorrt_jetson.sh /root/models 640
# 或宿主机 ~/icar_models
```

---

### 2.9 `rebuild_engine_with_nms.sh` + `generate_model_manifest.py`

**背景：** 组内 C++/框架侧常要求 **EfficientNMS** 四输出（count / boxes / scores / classes），并用 `model_manifest.json` 描述 binding。

| 脚本 | 功能 |
|------|------|
| `rebuild_engine_with_nms.sh` | 用 Ultralytics `nms=True` 重新导出 engine，再调用 manifest 生成脚本 |
| `generate_model_manifest.py` | 反序列化 engine，打印 binding；按训练类别固化 `labels`；写 `engine_sha256` 与 input/output 映射；**不猜类别名** |

类别顺序写死为训练 `data.yaml` 的 5 类，避免「假 foreign_object」。

---

## 3. ROS2 功能包详解（`icar_perception`）

包名：`icar_perception`（对齐立项报告与对接指南，替代早期 `icar_vision` 包名）。  
平台：ROS2 **Foxy**，Python（`rclpy`）。

### 3.1 `perception_node.py` — 核心检测节点

**订阅：**

- 图像话题（默认 `/image_raw`，参数可改）

**发布：**

- `/detections`：`vision_msgs/Detection2DArray`（组内标准接口）  
- `/vision/foreign_objects/summary`：字符串摘要（调试）  
- `/vision/foreign_objects/image`：可视化图（可选）

**每条检测至少包含：**

- `bbox.center.x/y`、`bbox.size_x/y`  
- `hypothesis.class_id`（类别字符串）  
- `hypothesis.score`（置信度）

**主要参数：**

| 参数 | 含义 | 默认 |
|------|------|------|
| `use_sim_detection` | true 时发假框，无需模型 | false |
| `model_path` | `.pt` / `.onnx` / `.engine` | `/root/models/yolo.engine` |
| `confidence_threshold` | 置信度阈值 | 0.5 |
| `input_size` | 网络输入边长 | 640 |
| `detection_rate_hz` | 推理频率上限 | 10.0 |
| `class_labels` | 类别名列表 | 五类异物 |

**其它逻辑：**

- 模拟模式：固定框 + 第一类标签，方便无硬件联调  
- 限帧：按 `detection_rate_hz` 节流  
- 周期性打印 `Inference FPS`（对接「≥10FPS」自查）

---

### 3.2 `foreign_object_avoidance.py` — 独立避障（课程演示用）

**用途：** 组内正式巡检的报警应由 `icar_mission` 做；本节点用于**个人演示**时近距离停车。

**订阅：** `/detections` + 深度图（可选）  
**发布：** `/cmd_vel`（置零停车）、`/vision/alarm`、`/vision/alarm_msg`

**判近逻辑：**

- 深度中心点距离 &lt; `stop_distance_m`，或  
- 检测框高度占比 ≥ `min_bbox_height_ratio`  

危险时持续发零速 Twist，直至清除。

---

### 3.3 Launch 与配置

| 文件 | 功能 |
|------|------|
| `launch/perception.launch.py` | 只启动 `perception_node`，供接入 bringup / 联调 `/detections` |
| `launch/vision_demo.launch.py` | 检测 + 避障两节点一齐起 |
| `config/perception_params.yaml` | 可交框架组嵌入的参数模板 |

**编译与启动示例：**

```bash
cd ~/icar_ws
colcon build --packages-select icar_perception
source install/setup.bash
ros2 launch icar_perception perception.launch.py use_sim_detection:=false
ros2 topic echo /detections
```

---

## 4. 依赖

**PC 训练（`requirements.txt`）：**

- ultralytics、opencv-python、numpy、Pillow、PyYAML、albumentations  

**小车 Docker / 宿主机：**

- ROS2 Foxy、`vision_msgs`、`cv_bridge`  
- ultralytics（加载 `.engine`）、系统 TensorRT  

**注意：** 部分 Jetson 镜像需将 NumPy 限制在 `&lt;1.24`，避免 TensorRT 与 `np.bool` 不兼容。

---

## 5. 推荐使用流程（简图）

```text
[演示场地拍照]
    → dataset/raw/<class>/*.jpg
    → run_all.py（标注/增强/训练/ONNX/评测）
    → models/best.pt + best.onnx
    → 拷到 Jetson ~/icar_models/
    → build_tensorrt_jetson.sh / Ultralytics export engine
    → best.engine
    → ros2 launch icar_perception perception.launch.py
    → /detections → 组内 mission 报警
```

---

## 6. 本代码包内容说明

压缩包 **`李yolo`** 包含上述**源代码、配置、launch、说明文档**。  

若体积限制，下列大体量二进制可能未包含或仅作占位，请在本地/小车原路径另存：

- `models/best.pt`、`models/best.onnx`、`.engine`  
- `models/runs/` 完整训练日志与权重  
- `交付包` 中已打包发给组长的大引擎文件  

类别定义与训练配置仍以仓库内 / 数据集侧 `data.yaml` 为准。

---

## 7. 作者

李子龙（23301006）  
课程项目：智能巡检小车 — 道面异物 YOLO 检测与 TensorRT 部署
