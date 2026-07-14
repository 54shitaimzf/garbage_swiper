# 手机热点遥控（当前端口）

Jetson 当前的 `8080` 已被官方相机网页占用，因此控制页面使用 `8081`。

1. 手机开启热点，让 Jetson 连接该热点；
2. 在 Jetson 执行 `WEB_CONTROL_PORT=8081 python3 /home/jetson/garbage_swiper_v2/jetson/web_control_gateway_v2.py`；
3. 查看 `hostname -I`，用手机浏览器打开 `http://<热点网段IP>:8081/`；
4. 车轮悬空、限速 30%，点击连接后短按方向键验证；
5. 松手、急停、离开页面或断网均应停止。

当前页面底层仍然使用官方 Rosmaster TCP `127.0.0.1:6000`，不直接操作串口。
