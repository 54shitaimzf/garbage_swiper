# 项目结构与路径约束

本项目同时包含电脑端工具、Jetson 车端服务、PWA 和 ROS2 源码。为保证现有控制链路不回归，本次整理不移动运行目录，只通过忽略规则和结构说明保持仓库清晰。

## 运行目录（不要移动或重命名）

| 目录 | 用途 | 车端对应位置 |
| --- | --- | --- |
| `web/` | 8081 手动控制页面、摇杆、视频和告警前端 | `/home/jetson/garbage_swiper_v2/web/` |
| `jetson/` | 8081 网关和 8082 启动脚本 | `/home/jetson/garbage_swiper_v2/jetson/` |
| `autonomy/` | 8082 自主任务服务和 PWA | `/home/jetson/garbage_swiper_v2/autonomy/` |
| `ros2_ws/` | ROS2 工作区源码 | `/home/jetson/icar_ws/src/` |
| `edge/` | `best.engine` 推理入口 | 车端使用 `/home/jetson/icar_models/best.engine` |
| `scripts/` | 训练、推理、协议和验证脚本 | 按脚本说明运行 |
| `cloud/` | MQTT 可选接口，默认不参与本地控制闭环 | 配置后再部署 |
| `android/` | 可选 Android 客户端源码 | 不影响当前 PWA |
| `reference/` | 官方手册和参考代码 | 只读参考 |

## 版本库内容边界

应提交：源码、配置、启动脚本、测试、文档和人类可读的 JSON/Markdown 验证记录。

不应提交：`*.engine`、`*.onnx`、`*.pt` 等模型文件，数据集，Python 缓存，日志，Android 构建产物，`.env`、密钥和证书，以及生成的图片/视频。

模型不放在仓库中。车端固定使用：

```text
/home/jetson/icar_models/best.engine
```

## 现有服务约束

- `6000`：官方底盘 TCP 服务。
- `8081`：旧手动控制链路，控制协议、页面、相机和告警入口保持不变。
- `8082`：新增自主任务入口，默认 mock 模式，不抢占 `8081` 的相机或串口。
- 地图使用车端白名单目录 `/home/jetson/icar_maps/`。
- ROS2 源码工作区使用车端 `/home/jetson/icar_ws/`。

## 整理原则

不移动 `web/`、`jetson/`、`autonomy/`、`ros2_ws/`、`edge/` 等运行目录，不修改已有硬编码的车端绝对路径，不修改 8081/8082 的运行代码。
