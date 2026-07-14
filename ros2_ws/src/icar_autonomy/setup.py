from setuptools import setup

package_name = "icar_autonomy"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/sensor_health.launch.py"]),
        ("share/" + package_name + "/config", ["config/autonomy_params.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    description="Read-only sensor health checks for safe ROS2 bringup",
    license="MIT",
    entry_points={
        "console_scripts": [
            "sensor_health = icar_autonomy.sensor_health:main",
        ],
    },
)
