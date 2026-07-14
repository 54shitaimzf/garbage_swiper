# 接口、端口与路径契约

## 1. 网络接口

| 端口 | 服务 | 作用 |
| --- | --- | --- |
| 6000 | 官方底盘 TCP | 运动控制 |
| 8081 | 旧手动网关 | 手动控制、WebSocket、视频、YOLO和告警 |
| 8082 | 自主任务服务 | 地图、任务状态和 PWA；默认 mock |

## 2. 8082 API

```text
GET  /api/maps
GET  /api/autonomy/status
POST /api/autonomy/activate
POST /api/autonomy/deactivate
POST /api/mission/map
POST /api/mission/start
POST /api/mission/stop
POST /api/mission/home
GET  /api/mapping/status
```

API 使用地图/路线 ID，不接受手机直接传入任意文件路径；禁用路线必须安全拒绝，不得驱动底盘。

## 3. ROS2 接口

传感器健康检查关注 `/scan`、`/odom`、`/tf`、彩色图像和深度图；感知方向使用 `/detections` 和视觉事件摘要。健康检查包不发布 `/cmd_vel`，不打开 `/dev/myserial`。

## 4. 云端主题

```text
robot/status
robot/battery
inspection/event
inspection/result
mission/command
```

默认使用 NullSink；MQTT 连接失败不得影响本地控制、告警和停车。
