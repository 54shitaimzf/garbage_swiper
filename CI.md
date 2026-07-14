# CI/CD verification

The repository workflow should run four independent checks:

1. Native Android Gradle assemble (`android/`), producing a debug APK.
2. Python protocol regression (`scripts/verify_protocol.py`).
3. YOLO runner syntax/import smoke with mocked inputs; the TensorRT engine test stays on Jetson.
4. ROS2 `colcon build` in an Ubuntu 20.04/Foxy container when the course runner is available.

Deployment to the Jetson remains an explicit SSH step. CI must not reboot the robot or start motors automatically.
