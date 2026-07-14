# icar_autonomy

The first ROS2 addition is intentionally read-only. `sensor_health` subscribes
to the official scan, odometry, TF, RGB and depth topics and publishes a JSON
health summary on `/icar/autonomy/sensor_health`.

It does not publish `/cmd_vel`, does not open `/dev/myserial`, and does not
replace the vendor bringup. Run it before enabling Nav2:

```bash
colcon build --packages-select icar_autonomy
source install/setup.bash
ros2 launch icar_autonomy sensor_health.launch.py
ros2 topic echo /icar/autonomy/sensor_health
```
