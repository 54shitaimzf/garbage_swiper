# 部署与运维手册

## 1. 固定部署约定

| 内容 | 车端位置 |
| --- | --- |
| 项目根目录 | `/home/jetson/garbage_swiper_v2` |
| 8081 手动网关 | `/home/jetson/garbage_swiper_v2/jetson/web_control_gateway_buzzer.py` |
| 8082 自主服务 | `/home/jetson/garbage_swiper_v2/autonomy/` |
| TensorRT 模型 | `/home/jetson/icar_models/best.engine` |
| 地图目录 | `/home/jetson/icar_maps/` |
| 官方底盘 | TCP 6000 |

## 2. 启动方式

```bash
# 旧手动链路
bash /home/jetson/garbage_swiper_v2/jetson/run_web_control_buzzer.sh

# 独立自主入口（当前默认 mock）
bash /home/jetson/garbage_swiper_v2/jetson/run_autonomy_8082.sh
```

启动后检查端口监听和浏览器 healthz；8082 不应覆盖 8081。

## 3. 发布与回滚

- Git 只提交源码、配置、测试和交付文档，不提交模型、数据集、密钥和日志。
- 远程部署前备份原 8081 网关；新增服务失败时只回滚 8082 文件。
- 8081 与 ROS2 底盘驱动不得同时占用同一串口；相机栈不得重复占用设备。
- ROS2/Nav2 真车部署前，确认 Jetson 已安装 `ros2`、`rclpy`、官方驱动和地图文件。
