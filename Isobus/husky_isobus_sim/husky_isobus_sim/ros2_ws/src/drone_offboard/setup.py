from setuptools import find_packages, setup

package_name = 'drone_offboard'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AgroDT',
    maintainer_email='research@example.invalid',
    description='Executor de missões PX4 X500 para o simulador agrícola AgroDT.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'mission_executor = drone_offboard.mission_executor:main',
        ],
    },
)
