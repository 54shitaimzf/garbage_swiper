# 手机热点启动命令

官方 Rosmaster 服务监听 Jetson 当前无线地址的 `6000`，控制网关也使用当前网卡地址连接它。手机热点切换后不要固定写旧 IP。

在 Jetson 执行：

```bash
CAR_IP=$(hostname -I | awk '{print $1}')
ROBOT_TCP_HOST="$CAR_IP" WEB_CONTROL_PORT=8081 \
  python3 /home/jetson/garbage_swiper_v2/jetson/web_control_gateway_v2.py \
  > /home/jetson/garbage_swiper_v2/gateway.log 2>&1 &
```

然后手机连接同一热点，访问 `http://$CAR_IP:8081/`。首次测试车轮悬空、限速 30%。
