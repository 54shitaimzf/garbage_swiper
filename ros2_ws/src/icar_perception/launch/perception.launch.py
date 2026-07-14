"""Launch icar_perception node (team standard: /detections)."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('icar_perception')
    default_config = os.path.join(pkg_share, 'config', 'perception_params.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=default_config),
        DeclareLaunchArgument('use_sim_detection', default_value='false'),
        DeclareLaunchArgument('model_path', default_value='/root/models/yolo.engine'),
        DeclareLaunchArgument('image_topic', default_value='/image_raw'),
        DeclareLaunchArgument('detection_topic', default_value='/detections'),
        DeclareLaunchArgument('confidence_threshold', default_value='0.5'),
        DeclareLaunchArgument('input_size', default_value='640'),
        DeclareLaunchArgument('detection_rate_hz', default_value='10.0'),
        Node(
            package='icar_perception',
            executable='perception_node',
            name='perception_node',
            output='screen',
            parameters=[
                LaunchConfiguration('config'),
                {
                    'use_sim_detection': LaunchConfiguration('use_sim_detection'),
                    'model_path': LaunchConfiguration('model_path'),
                    'image_topic': LaunchConfiguration('image_topic'),
                    'detection_topic': LaunchConfiguration('detection_topic'),
                    'confidence_threshold': LaunchConfiguration('confidence_threshold'),
                    'input_size': LaunchConfiguration('input_size'),
                    'detection_rate_hz': LaunchConfiguration('detection_rate_hz'),
                    'publish_image': False,
                },
            ],
        ),
    ])
