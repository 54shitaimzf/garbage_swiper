# 手机热点遥控

使用 `jetson/run_web_control_v2.sh` 启动网页控制网关。手机与 Jetson 连接同一手机热点后，用浏览器访问：

`http://<Jetson 在手机热点中的 IP>:8080/`

网页只连接 Jetson 的 WebSocket；Jetson 使用官方 Rosmaster ASCII-hex TCP 协议连接本机 `127.0.0.1:6000`。网关包含松手、断线和 1 秒无控制帧自动零速/急停保护。

手动模式启动前不要运行 ROS2 底盘驱动，因为两者不能同时占用 `/dev/myserial`。
