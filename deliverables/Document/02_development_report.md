# 系统设计与开发报告

## 1. 总体架构

```text
手机浏览器/PWA
├── 8081 手动控制 → WebSocket → 手动网关 → TCP 6000 → Rosmaster
│                                      └→ 摄像头 / best.engine / 本地告警
└── 8082 自主任务 → 地图与任务 API → 当前 mock 状态机

ROS2 扩展：官方驱动 → /scan /odom /tf /camera topics
                         └→ icar_autonomy 只读健康检查

云端扩展：状态/事件 → NullSink 或 MqttSink → MQTT Broker
```

## 2. 模块职责

| 模块 | 目录 | 作用 |
| --- | --- | --- |
| 手动控制 | `web/`、`jetson/` | 8081 页面、WebSocket、视频、底盘控制和告警 |
| 自主入口 | `autonomy/` | 8082 PWA、地图白名单、任务状态和安全 API |
| 边缘推理 | `edge/`、车端模型路径 | 使用 `best.engine` 产生识别结果 |
| ROS2 感知 | `ros2_ws/src/icar_perception/` | 检测接口和独立避障演示 |
| ROS2 健康检查 | `ros2_ws/src/icar_autonomy/` | 只读检查传感器、TF 和图像链路 |
| 云端接口 | `cloud/` | MQTT 可选输出，默认不参与本地闭环 |

## 3. 安全与可维护性

1. 8081 旧链路和 8082 新服务分进程、分端口，避免新增功能覆盖原控制协议。
2. 8082 mock 模式不接触电机、相机和串口；ROS2 不可用时 fail-closed。
3. 手动/自主切换必须先零速，确认资源释放后再启动目标模式。
4. MQTT 只发布状态和事件，不能绕过本地急停逻辑直接控制底盘。
5. 模型、地图、密钥和运行日志与源码分离，部署路径保持固定。

## 4. 开发取舍

当前演示以 8081 手动控制、视频、`best.engine` 和告警为稳定闭环；自主导航、SLAM 和融合按独立批次接入，避免影响已验证功能。
