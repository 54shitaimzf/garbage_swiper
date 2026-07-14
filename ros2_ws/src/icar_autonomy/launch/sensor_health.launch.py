from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="icar_autonomy",
                executable="sensor_health",
                name="icar_sensor_health",
                output="screen",
            )
        ]
    )
