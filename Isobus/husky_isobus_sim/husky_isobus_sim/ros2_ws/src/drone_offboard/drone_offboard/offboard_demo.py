#!/usr/bin/env python3
"""Take off, hover, then land a PX4 X500 using the ROS 2 uXRCE-DDS bridge."""

import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand
from px4_msgs.msg import VehicleLocalPosition, VehicleStatus


def px4_topic(base_topic, msg_type):
    """Return the DDS topic name used by the installed px4_msgs version."""
    version = int(getattr(msg_type, 'MESSAGE_VERSION', 0))
    if version > 0:
        return f'{base_topic}_v{version}'
    return base_topic


class OffboardDemo(Node):
    def __init__(self):
        super().__init__('x500_offboard_demo')
        self.declare_parameter('takeoff_height_m', 3.0)
        self.declare_parameter('hover_seconds', 8.0)
        self.takeoff_height = float(self.get_parameter('takeoff_height_m').value)
        self.hover_seconds = float(self.get_parameter('hover_seconds').value)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.offboard_pub = self.create_publisher(
            OffboardControlMode, '/fmu/in/offboard_control_mode', qos)
        self.trajectory_pub = self.create_publisher(
            TrajectorySetpoint, '/fmu/in/trajectory_setpoint', qos)
        self.command_pub = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', qos)

        self.local_position_topic = px4_topic(
            '/fmu/out/vehicle_local_position', VehicleLocalPosition)
        self.vehicle_status_topic = px4_topic(
            '/fmu/out/vehicle_status', VehicleStatus)

        self.get_logger().info(
            f'PX4 local position: {self.local_position_topic}')
        self.get_logger().info(
            f'PX4 vehicle status: {self.vehicle_status_topic}')

        self.create_subscription(
            VehicleLocalPosition, self.local_position_topic,
            self._local_position_cb, qos)
        self.create_subscription(
            VehicleStatus, self.vehicle_status_topic,
            self._status_cb, qos)

        self.local_position = VehicleLocalPosition()
        self.vehicle_status = VehicleStatus()
        self.have_position = False
        self.have_status = False
        self.counter = 0
        self.takeoff_reached_at = None
        self.land_sent_at = None
        self.home_x = 0.0
        self.home_y = 0.0
        self.home_captured = False
        self.timer = self.create_timer(0.1, self._tick)
        self.get_logger().info(
            f'Demo pronto: subir {self.takeoff_height:.1f} m, '
            f'pairar {self.hover_seconds:.1f} s e pousar.')

    def _timestamp_us(self):
        return int(self.get_clock().now().nanoseconds / 1000)

    def _local_position_cb(self, msg):
        self.local_position = msg
        self.have_position = True
        if not self.home_captured and math.isfinite(float(msg.x)) and math.isfinite(float(msg.y)):
            self.home_x = float(msg.x)
            self.home_y = float(msg.y)
            self.home_captured = True
            self.get_logger().info(
                f'Origem local capturada: x={self.home_x:.2f}, y={self.home_y:.2f}')

    def _status_cb(self, msg):
        self.vehicle_status = msg
        self.have_status = True

    def _heartbeat(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = self._timestamp_us()
        self.offboard_pub.publish(msg)

    def _setpoint(self, x, y, z, yaw=0.0):
        msg = TrajectorySetpoint()
        msg.position = [float(x), float(y), float(z)]
        msg.yaw = float(yaw)
        msg.timestamp = self._timestamp_us()
        self.trajectory_pub.publish(msg)

    def _vehicle_command(self, command, param1=0.0, param2=0.0):
        msg = VehicleCommand()
        msg.command = int(command)
        msg.param1 = float(param1)
        msg.param2 = float(param2)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self._timestamp_us()
        self.command_pub.publish(msg)

    def _arm_and_offboard(self):
        self._vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)
        self._vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.get_logger().info('Comandos OFFBOARD + ARM enviados.')

    def _land(self):
        self._vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.land_sent_at = time.monotonic()
        self.get_logger().info('Comando LAND enviado.')

    def _tick(self):
        self._heartbeat()

        # NED: z negativo significa subir.
        target_z = -abs(self.takeoff_height)
        self._setpoint(self.home_x, self.home_y, target_z, 0.0)

        # PX4 exige fluxo de setpoints antes de aceitar OFFBOARD.
        if self.counter == 10:
            self._arm_and_offboard()
        if self.counter < 11:
            self.counter += 1

        if self.land_sent_at is not None:
            if time.monotonic() - self.land_sent_at > 8.0:
                self.get_logger().info('Demo encerrado.')
                rclpy.shutdown()
            return

        if not self.have_position:
            return

        z = float(self.local_position.z)
        if math.isfinite(z) and z <= target_z + 0.35:
            if self.takeoff_reached_at is None:
                self.takeoff_reached_at = time.monotonic()
                self.get_logger().info('Altitude de demonstração atingida; pairando.')
            elif time.monotonic() - self.takeoff_reached_at >= self.hover_seconds:
                self._land()


def main(args=None):
    rclpy.init(args=args)
    node = OffboardDemo()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node._vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
