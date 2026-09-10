from setuptools import find_packages, setup

package_name = 'husky_isobus_bridge'

setup(
    name=package_name,
    version='2.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'PyYAML', 'python-can'],
    zip_safe=True,
    maintainer='Projeto Husky ISOBUS',
    maintainer_email='noreply@example.invalid',
    description='Ponte mínima Husky A200 ROS 2 Odometry para SocketCAN/vcan0.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'python_can_bridge = husky_isobus_bridge.bridge_node:main',
            'vcan_motion_monitor = husky_isobus_bridge.monitor:main',
        ],
    },
)
