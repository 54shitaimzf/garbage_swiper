"""Standalone demo: perception + local emergency stop."""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model_path', default_value='/root/models/yolo.engine'),
        DeclareLaunchArgument('image_topic', default_value='/image_raw'),
        DeclareLaunchArgument('depth_topic', default_value='/camera/depth/image_raw'),
        DeclareLaunchArgument('detection_topic', default_value='/detections'),
        DeclareLaunchArgument('confidence_threshold', default_value='0.5'),
        DeclareLaunchArgument('stop_distance_m', default_value='0.85'),
        DeclareLaunchArgument('min_bbox_height_ratio', default_value='0.28'),
        DeclareLaunchArgument('image_height', default_value='480.0'),
        Node(
            package='icar_perception',
            executable='perception_node',
            name='perception_node',
            output='screen',
            parameters=[{
                'use_sim_detection': False,
                'model_path': LaunchConfiguration('model_path'),
                'image_topic': LaunchConfiguration('image_topic'),
                'detection_topic': LaunchConfiguration('detection_topic'),
                'confidence_threshold': LaunchConfiguration('confidence_threshold'),
                'input_size': 640,
                'detection_rate_hz': 10.0,
                'publish_image': True,
            }],
        ),
        Node(
            package='icar_perception',
            executable='foreign_object_avoidance',
            name='foreign_object_avoidance',
            output='screen',
            parameters=[{
                'detection_topic': LaunchConfiguration('detection_topic'),
                'depth_topic': LaunchConfiguration('depth_topic'),
                'cmd_vel_topic': '/cmd_vel',
                'stop_distance_m': LaunchConfiguration('stop_distance_m'),
                'min_bbox_height_ratio': LaunchConfiguration('min_bbox_height_ratio'),
                'image_height': LaunchConfiguration('image_height'),
                'conf_threshold': LaunchConfiguration('confidence_threshold'),
                'use_depth': True,
            }],
        ),
    ])
