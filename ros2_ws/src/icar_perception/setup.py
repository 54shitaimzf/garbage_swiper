from setuptools import setup

package_name = 'icar_perception'

setup(
    name=package_name,
    version='0.3.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/perception.launch.py',
            'launch/vision_demo.launch.py',
        ]),
        ('share/' + package_name + '/config', [
            'config/perception_params.yaml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lizilong',
    maintainer_email='student@example.com',
    description='YOLO foreign object detection for iCar inspection system',
    license='MIT',
    entry_points={
        'console_scripts': [
            'perception_node = icar_perception.perception_node:main',
            'foreign_object_avoidance = icar_perception.foreign_object_avoidance:main',
        ],
    },
)
