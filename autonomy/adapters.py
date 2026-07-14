"""Mission adapters.

The mock adapter is the only default.  The ROS2 adapter is deliberately
optional and never silently falls back to motion simulation in ROS2 mode.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


class AdapterError(RuntimeError):
    """Raised when an adapter cannot safely perform an operation."""


@dataclass
class AdapterStatus:
    mode: str
    available: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "available": self.available,
            "message": self.message,
        }


class MockAdapter:
    """Non-hardware adapter used for API and PWA verification."""

    def __init__(self, duration_sec: float = 1.0, on_complete: Callable[[str], None] | None = None) -> None:
        self.duration_sec = max(0.0, duration_sec)
        self.on_complete = on_complete
        self._timers: list[threading.Timer] = []

    def status(self) -> AdapterStatus:
        return AdapterStatus("mock", True, "模拟模式：不会发送底盘指令")

    def activate(self) -> None:
        return None

    def deactivate(self) -> None:
        self.cancel()

    def start(self, mission_id: str, waypoints: list[dict[str, float]]) -> None:
        if not waypoints:
            raise AdapterError("route has no calibrated waypoints")
        if self.on_complete is not None:
            timer = threading.Timer(self.duration_sec, self.on_complete, args=(mission_id,))
            timer.daemon = True
            timer.start()
            self._timers.append(timer)

    def cancel(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()

    def home(self) -> None:
        return None

    def start_mapping(self) -> None:
        return None

    def stop_mapping(self) -> None:
        return None

    def shutdown(self) -> None:
        self.cancel()


class Ros2Adapter:
    """Optional Nav2 action adapter.

    This implementation only becomes selectable when ROS2 Python bindings and
    Nav2 action types are installed.  It intentionally does not start vendor
    drivers or claim the serial/camera devices; that handoff belongs to the
    future mode supervisor and must be verified on the Jetson first.
    """

    def __init__(self, on_state: Callable[[str, str], None] | None = None) -> None:
        self.on_state = on_state
        self._available = False
        self._message = "ROS2 bindings not loaded"
        self._node = None
        self._action_client = None
        self._goal_handle = None
        self._executor_thread: threading.Thread | None = None
        try:
            import rclpy  # type: ignore
            from nav2_msgs.action import NavigateToPose  # type: ignore
            from rclpy.action import ActionClient  # type: ignore
            from rclpy.executors import MultiThreadedExecutor  # type: ignore

            self._rclpy = rclpy
            self._NavigateToPose = NavigateToPose
            self._ActionClient = ActionClient
            self._MultiThreadedExecutor = MultiThreadedExecutor
            self._available = True
            self._message = "ROS2 bindings available; vendor handoff not started"
        except ImportError as exc:
            self._message = f"ROS2 unavailable: {exc}"

    def status(self) -> AdapterStatus:
        return AdapterStatus("ros2", self._available, self._message)

    def activate(self) -> None:
        if not self._available:
            raise AdapterError(self._message)
        if self._node is not None:
            return
        self._rclpy.init(args=None)
        self._node = self._rclpy.create_node("icar_autonomy_gateway")
        self._action_client = self._ActionClient(self._node, self._NavigateToPose, "navigate_to_pose")
        executor = self._MultiThreadedExecutor()
        executor.add_node(self._node)
        self._executor_thread = threading.Thread(target=executor.spin, daemon=True)
        self._executor_thread.start()
        self._message = "ROS2 gateway ready; vendor bringup must already be healthy"

    def deactivate(self) -> None:
        self.cancel()
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        if self._rclpy.ok():
            self._rclpy.shutdown()
        self._action_client = None
        self._message = "ROS2 gateway inactive"

    def start(self, mission_id: str, waypoints: list[dict[str, float]]) -> None:
        if self._node is None or self._action_client is None:
            raise AdapterError("ROS2 gateway is not active")
        if not waypoints:
            raise AdapterError("route has no calibrated waypoints")
        if not self._action_client.wait_for_server(timeout_sec=2.0):
            raise AdapterError("Nav2 navigate_to_pose action is unavailable")
        self._send_waypoint(mission_id, waypoints, 0)

    def _send_waypoint(self, mission_id: str, waypoints: list[dict[str, float]], index: int) -> None:
        point = waypoints[index]
        goal = self._NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(point["x"])
        goal.pose.pose.position.y = float(point["y"])
        import math

        goal.pose.pose.orientation.z = math.sin(float(point["yaw"]) / 2.0)
        goal.pose.pose.orientation.w = math.cos(float(point["yaw"]) / 2.0)
        future = self._action_client.send_goal_async(goal)
        future.add_done_callback(
            lambda completed: self._goal_sent(completed, mission_id, waypoints, index)
        )

    def _goal_sent(self, future: Any, mission_id: str, waypoints: list[dict[str, float]], index: int) -> None:
        try:
            self._goal_handle = future.result()
        except Exception as exc:  # pragma: no cover - depends on ROS2 runtime
            if self.on_state:
                self.on_state("error", str(exc))
            return
        if not self._goal_handle.accepted:
            if self.on_state:
                self.on_state("error", "Nav2 rejected goal")
            return
        result_future = self._goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda completed: self._goal_result(completed, mission_id, waypoints, index)
        )

    def _goal_result(self, future: Any, mission_id: str, waypoints: list[dict[str, float]], index: int) -> None:
        try:
            result = future.result().result
            success = getattr(result, "result", 1) == 0
        except Exception as exc:  # pragma: no cover - depends on ROS2 runtime
            success = False
            if self.on_state:
                self.on_state("error", str(exc))
        if not success:
            if self.on_state:
                self.on_state("error", f"Nav2 goal failed at waypoint {index}")
            return
        if index + 1 < len(waypoints):
            self._send_waypoint(mission_id, waypoints, index + 1)
        elif self.on_state:
            self.on_state("succeeded", mission_id)

    def cancel(self) -> None:
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None

    def home(self) -> None:
        raise AdapterError("home route is not configured")

    def start_mapping(self) -> None:
        raise AdapterError("SLAM lifecycle is not connected until vendor bringup is verified")

    def stop_mapping(self) -> None:
        raise AdapterError("SLAM lifecycle is not connected until vendor bringup is verified")

    def shutdown(self) -> None:
        self.deactivate()
