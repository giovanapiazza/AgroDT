from setuptools import find_packages, setup

package_name = 'drone_offboard'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AgroDT',
    maintainer_email='research@example.invalid',
    description='PX4 X500 offboard demo for AgrobotScene.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'offboard_demo = drone_offboard.offboard_demo:main',
        ],
    },
)
