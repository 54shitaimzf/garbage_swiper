# iCar 智能小车 — 控制链路开发文档

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  APP (Android/Java)                                                  │
│                                                                      │
│  RockerView.java        CarEncode.java      TCPClientManager.java   │
│  (触摸→坐标映射)  ──→   (协议编码)    ──→    (TCP单例 :6001)        │
│                                                                      │
│  摇杆 touch → [-100,100] → "$0110xxyyCK#" → socket.send()           │
│  按钮 click → CarDirection → "$0115xxCK#"    → socket.send()        │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ TCP :6001
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  小车宿主机 (Jetson Orin Nano / Ubuntu 20.04)                        │
│                                                                      │
│  tcp_proxy.py (:6001)  ──→  Rosmaster app.py (:6000)                │
│  (多客户端代理)              (单连接, listen(1))                     │
│                                        │                             │
│                                        ▼                             │
│                                /dev/ttyUSB1 (115200)                 │
│                                        │                             │
│                                        ▼                             │
│                              MCU (AT32F403A)  ──→  4路电机           │
└──────────────────────────────────────────────────────────────────────┘
```

## 二、通信协议

### 报文格式

```
$ 01 TYPE SIZE DATA CHECKSUM #
│  │  │    │    │    │        │
│  │  │    │    │    │        └── 结束符 '#'
│  │  │    │    │    └─────────── 校验和 (所有字节求和 % 256, 2字符hex)
│  │  │    │    └──────────────── 数据内容 (hex字符串, 变长)
│  │  │    └───────────────────── 数据长度 = len(DATA) + 2 (2字符hex)
│  │  └────────────────────────── 命令类型 (2字符hex)
│  └───────────────────────────── 固定前缀 "01"
└──────────────────────────────── 起始符 '$'
```

**示例**: `$011006500067#`

| 字段 | 值 | 含义 |
|------|-----|------|
| `$` | - | 帧头 |
| `01` | - | 固定前缀 |
| `10` | TYPE | 摇杆控制 |
| `06` | SIZE | 数据长度 6 (4字节数据 + 2) |
| `5000` | DATA | speed_x=80(0x50), speed_y=0(0x00) |
| `67` | CK | checksum = (01+10+06+50+00) % 256 = 0x67 |
| `#` | - | 帧尾 |

### 命令表

| TYPE | 命令 | DATA | 说明 |
|------|------|------|------|
| `01` | 查询硬件版本 | 无 | - |
| `02` | 查询电池电压 | 无 | - |
| `0F` | 进入页面 | page(2hex) | 通知小车当前页面 |
| `10` | 摇杆控制 | speed_x(2hex) + speed_y(2hex) | -100~100, 负数用 v+256 |
| `15` | 按钮方向 | direction(2hex) | 见方向表 |
| `16` | 设置速度 | xy_speed(2hex) + z_speed(2hex) | 0~100 |
| `21` | 四轮独立速度 | L1+L2+R1+R2(各2hex) | -100~100 |
| `60` | 拍照 | 无 | - |
| `61` | 开始录像 | 无 | - |
| `62` | 结束录像 | 无 | - |
| `63` | 开始循迹 | 无 | MCU 固件 follow-line.bin |
| `64` | 关闭循迹 | 无 | - |

### 方向编码 (TYPE 15)

| 值 | 方向 |
|----|------|
| 0 | 停止 |
| 1 | 前进 |
| 2 | 后退 |
| 3 | 左移 |
| 4 | 右移 |
| 5 | 左转 |
| 6 | 右转 |
| 7 | 急停 |

### 负数编码规则

```
Java:  v < 0 ? v + 256 : v
示例:  -100 → -100 + 256 = 156 = 0x9C → "9C"
```

## 三、APP 端控制流程

### 3.1 摇杆控制链路

```
RockerView.onTouchEvent()
  ├─ ACTION_DOWN  → 记录按下, 检测双击
  ├─ ACTION_MOVE  → updateFinger(tx, ty)
  │    ├─ 限制触摸点在圆形底座内
  │    ├─ 坐标映射: 圆内坐标 → [-100, 100]
  │    └─ listener.onTilt(tiltX, tiltY)
  │         │
  │         ▼
  │    RemoteControlActivity:
  │      sx = tiltX * speedPercent / 100   // 速度百分比缩放
  │      sy = tiltY * speedPercent / 100
  │      tcp.send(CarEncode.ctrlCar(sx, sy))
  │         │
  │         ▼
  │    CarEncode.ctrlCar():
  │      sx < 0 ? sx += 256                // 负数编码
  │      sy < 0 ? sy += 256
  │      → "$011006XXYYCK#"                // 拼接协议帧
  │         │
  │         ▼
  │    TCPClientManager.send():
  │      executor.execute(() -> {
  │        out.write(message + "\n")        // 异步发送,防ANR
  │        out.flush()
  │      })
  │
  ├─ ACTION_UP    → 摇杆回中, 发零速(0,0)
  └─ 双击         → 急停 (零速 + Brake)
```

### 3.2 速度控制

```java
// SeekBar 0→100, 默认 40%
sbSpeed.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
    public void onProgressChanged(SeekBar bar, int p, boolean fromUser) {
        speedPercent = p;
        tcp.send(CarEncode.setSpeed(p, p));   // 发速度设置命令
    }
});
```

### 3.3 按钮控制链路

```
Button onClick()
  ├─ 前进: tcp.send(CarEncode.buttonCar(CarDirection.Front))
  ├─ 后退: tcp.send(CarEncode.buttonCar(CarDirection.After))
  ├─ 左移: tcp.send(CarEncode.buttonCar(CarDirection.Left))
  ├─ 右移: tcp.send(CarEncode.buttonCar(CarDirection.Right))
  ├─ 左转: tcp.send(CarEncode.buttonCar(CarDirection.LeftRotate))
  ├─ 右转: tcp.send(CarEncode.buttonCar(CarDirection.RightRotate))
  └─ 停止: tcp.send(CarEncode.buttonCar(CarDirection.Stop))

每个按钮: onTouchListener → ACTION_DOWN 发方向, ACTION_UP 发 Stop
持续按下 = 持续发送 (靠 ACTION_DOWN 单次发送, 小车维持)
```

### 3.4 拍照/录像

```java
btnPhoto.onClick() → tcp.send(CarEncode.takePhotos())      // TYPE 60
btnRecord.onClick() → 切换状态:
  if (!isRecording) tcp.send(CarEncode.startRecording())   // TYPE 61
  else              tcp.send(CarEncode.closeRecording())    // TYPE 62
```

## 四、小车端控制链路

### 4.1 tcp_proxy.py — 多客户端代理

```
APP ──→ :6001 (tcp_proxy) ──→ :6000 (Rosmaster)
             │
             ├─ _forward_from_client(): 客户端→Rosmaster
             ├─ _read_loop():           Rosmaster→广播所有客户端
             └─ 自动重连: Rosmaster 断开时自动重连
```

**为什么需要 proxy**: Rosmaster `sock.listen(1)` 只接受 1 个 TCP 连接。proxy 允许多个客户端（APP + cmd_vel_bridge 等）同时连接。

### 4.2 Rosmaster 串口通信

```
TCP :6000 收到 "$011006500067#"
  → 解析协议帧
  → 提取 TYPE=10, speed_x=80(0x50), speed_y=0(0x00)
  → 组包为 MCU 串口协议
  → /dev/ttyUSB1 @115200bps
  → MCU(AT32F403A) 解析 → PWM → 电机驱动
```

### 4.3 cmd_vel_bridge.py — ROS2→小车桥接

```
ROS2 /cmd_vel (Twist) → cmd_vel_bridge.py
  → linear.x, angular.z → 转换为摇杆协议
  → "$0110xxyyCK#" → TCP :6001 → tcp_proxy → Rosmaster → 电机
```

安全超时: 2 秒收不到 `/cmd_vel` 自动发零速停止。

## 五、关键设计决策

| 决策 | 原因 |
|------|------|
| TCP 文本协议 (ASCII Hex) | 与 MCU 固件保持一致, 易调试 |
| 单例 TCPClientManager | 全局共享一个连接, 避免端口冲突 |
| 异步发送 (writeExecutor) | Android 不允许主线程网络 IO |
| 摇杆坐标映射 [-100, 100] | 线性映射, 速度百分比在 APP 层缩放 |
| tcp_proxy 多客户端代理 | Rosmaster listen(1) 限制 |
| 负数 +256 编码 | 单字节无符号传输, 恢复时有符号解释 |

## 六、文件索引

| 文件 | 位置 | 功能 |
|------|------|------|
| `CarEncode.java` | android/.../protocol/ | 11条命令的协议编码 |
| `CarDirection.java` | android/.../protocol/ | 8方向枚举 |
| `TCPClientManager.java` | android/.../tcp/ | TCP 单例, 异步收发 |
| `RockerView.java` | android/.../view/ | Canvas 自定义摇杆 |
| `RemoteControlActivity.java` | android/.../ | 遥控页(摇杆/按钮/视频/激光) |
| `tcp_proxy.py` | car_server/ | 多客户端代理 |
| `cmd_vel_bridge.py` | car_server/ | ROS2 /cmd_vel → TCP |
| `CarEnum.ets` | entry/.../CarUtill/ | HarmonyOS 版协议(参考) |

## 七、调试技巧

```bash
# 小车端抓包
ss -tnp | grep :6001          # 看有几个 APP 连接
tcpdump -i lo port 6000 -X    # 抓 Rosmaster 通信

# APP 端看日志
adb logcat | grep CarEncode   # 看协议编码
adb logcat | grep TCPClient   # 看连接状态

# 测试命令
echo '$011006500067#' | nc 192.168.43.162 6000   # 直发摇杆命令
curl http://192.168.43.162:8765/stop             # 急停激光
```
