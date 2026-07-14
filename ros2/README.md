# ROS2 official-interface integration

The ROS2 mode uses the vendor Foxy packages already installed on the Jetson:

- `icar_bringup` / `Mcnamu_driver_X3.py` owns `/dev/myserial` and publishes odometry, joint state and IMU.
- `sllidar_ros2` owns `/dev/rplidar` and publishes `/scan`.
- Astra official SDK publishes RGB/depth topics when the camera node is enabled.
- Nav2 consumes `/scan`, `/odom` and the TF tree.

## Mutually exclusive control modes

1. Manual acceptance mode: Android -> official TCP `10.71.253.19:6000` -> Rosmaster. Do not launch the ROS2 base driver at the same time.
2. Autonomous ROS2 mode: stop the TCP owner, launch the official `icar_bringup_X3_launch.py`, lidar, camera and Nav2. A future gateway can expose mission commands to Android without putting DDS on the phone.

Only one process may own `/dev/myserial`, and only one camera stack may own the Astra device.

## Interfaces to freeze

`/cmd_vel`, `/scan`, `/odom`, `/tf`, `/tf_static`, `/camera/color/image_raw`, `/camera/depth/image_raw`, `/camera/depth_to_color/image_raw`.

The perception node should publish a small JSON-compatible event containing timestamp, class, confidence, bounding box and optional depth distance. It should not modify vendor packages.
