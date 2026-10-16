#!/usr/bin/env python3
"""Executa missões JSON de waypoints em um PX4 X500 via ROS 2 Offboard."""

import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from std_msgs.msg import String
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleCommandAck,
    VehicleLocalPosition,
    VehicleStatus,
)


def px4_topic(base_topic, msg_type):
    version = int(getattr(msg_type, "MESSAGE_VERSION", 0))
    return f"{base_topic}_v{version}" if version > 0 else base_topic


class MissionExecutor(Node):
    def __init__(self):
        super().__init__("agrodt_drone_mission_executor")

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.offboard_pub = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", qos)
        self.trajectory_pub = self.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", qos)
        self.command_pub = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", qos)

        self.create_subscription(
            VehicleLocalPosition,
            px4_topic("/fmu/out/vehicle_local_position", VehicleLocalPosition),
            self._position_cb,
            qos,
        )
        self.create_subscription(
            VehicleStatus,
            px4_topic("/fmu/out/vehicle_status", VehicleStatus),
            self._status_cb,
            qos,
        )
        self.create_subscription(
            VehicleCommandAck,
            px4_topic("/fmu/out/vehicle_command_ack", VehicleCommandAck),
            self._ack_cb,
            qos,
        )
        self.create_subscription(
            String, "/agrodt/drone/mission", self._mission_cb, 10)

        self.status_pub = self.create_publisher(
            String, "/agrodt/drone/mission_status", 10)

        self.position = None
        self.vehicle_status = None
        self.mission_id = None
        self.waypoints = []
        self.current_index = 0
        self.tolerance = 0.6
        self.hold_seconds = 1.0
        self.auto_land = True
        self.state = "IDLE"
        self.prestream_count = 0
        self.reached_since = None
        self.land_sent_at = None
        self.activation_started_at = None
        self.last_activation_command_at = 0.0
        self.activation_retries = 0

        self.create_timer(0.1, self._tick)
        self.get_logger().info(
            "Executor pronto. Aguardando JSON em /agrodt/drone/mission")

    def _timestamp_us(self):
        return int(self.get_clock().now().nanoseconds / 1000)

    def _position_cb(self, msg):
        self.position = msg

    def _status_cb(self, msg):
        self.vehicle_status = msg

    def _ack_cb(self, msg):
        names = {
            VehicleCommandAck.VEHICLE_CMD_RESULT_ACCEPTED: "ACCEPTED",
            VehicleCommandAck.VEHICLE_CMD_RESULT_TEMPORARILY_REJECTED: "TEMP_REJECTED",
            VehicleCommandAck.VEHICLE_CMD_RESULT_DENIED: "DENIED",
            VehicleCommandAck.VEHICLE_CMD_RESULT_UNSUPPORTED: "UNSUPPORTED",
            VehicleCommandAck.VEHICLE_CMD_RESULT_FAILED: "FAILED",
            VehicleCommandAck.VEHICLE_CMD_RESULT_IN_PROGRESS: "IN_PROGRESS",
            VehicleCommandAck.VEHICLE_CMD_RESULT_CANCELLED: "CANCELLED",
        }
        result_name = names.get(int(msg.result), str(int(msg.result)))
        self.get_logger().info(
            f"PX4 ACK command={int(msg.command)} result={result_name} "
            f"param1={int(msg.result_param1)} param2={int(msg.result_param2)}"
        )
        self._publish_status(
            "command_ack",
            command=int(msg.command),
            result=result_name,
        )

    def _publish_status(self, status, **extra):
        payload = {"mission_id": self.mission_id, "status": status, **extra}
        if status == "completed":
            payload["command"] = "end_mission"
        msg = String()
        msg.data = json.dumps(payload, separators=(",", ":"))
        self.status_pub.publish(msg)
        self.get_logger().info(msg.data)

    def _mission_cb(self, msg):
        if self.state not in ("IDLE", "COMPLETED", "FAILED"):
            self._publish_status("rejected", reason="mission_already_running")
            return

        try:
            data = json.loads(msg.data)
            payload = data.get("payload", {})

            if payload.get("command") != "start_mission":
                raise ValueError("payload.command deve ser start_mission")

            raw_waypoints = payload.get("waypoints", [])
            if not raw_waypoints:
                raise ValueError("a missão não possui waypoints")

            self.waypoints = [
                {
                    "x": float(wp["x"]),
                    "y": float(wp["y"]),
                    "z": float(wp["z"]),
                    "yaw": float(wp.get("yaw", 0.0)),
                }
                for wp in raw_waypoints
            ]

            self.mission_id = data.get("mission_id", 0)
            self.tolerance = float(payload.get("tolerance_m", 0.6))
            self.hold_seconds = float(payload.get("hold_seconds", 1.0))
            self.auto_land = bool(payload.get("auto_land", True))
            self.current_index = 0
            self.prestream_count = 0
            self.reached_since = None
            self.land_sent_at = None
            self.activation_started_at = None
            self.last_activation_command_at = 0.0
            self.activation_retries = 0
            self.state = "PRESTREAM"

            self._publish_status(
                "accepted",
                waypoint_count=len(self.waypoints),
            )

        except Exception as exc:
            self._publish_status("rejected", reason=str(exc))

    def _heartbeat(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = self._timestamp_us()
        self.offboard_pub.publish(msg)

    def _setpoint(self, waypoint):
        msg = TrajectorySetpoint()
        msg.position = [
            float(waypoint["x"]),
            float(waypoint["y"]),
            float(waypoint["z"]),
        ]
        msg.yaw = float(waypoint.get("yaw", 0.0))
        msg.timestamp = self._timestamp_us()
        self.trajectory_pub.publish(msg)

    def _vehicle_command(self, command, param1=0.0, param2=0.0):
        msg = VehicleCommand()
        msg.command = int(command)
        msg.param1 = float(param1)
        msg.param2 = float(param2)
        msg.param3 = 0.0
        msg.param4 = 0.0
        msg.param5 = 0.0
        msg.param6 = 0.0
        msg.param7 = 0.0
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self._timestamp_us()
        self.command_pub.publish(msg)

    def _send_activation_commands(self):
        self._vehicle_command(
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
            1.0,
            6.0,
        )
        self._vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
            1.0,
        )
        self.last_activation_command_at = time.monotonic()
        self.activation_retries += 1
        self.get_logger().info(
            f"Solicitando OFFBOARD + ARM (tentativa {self.activation_retries})"
        )

    def _is_offboard_and_armed(self):
        if self.vehicle_status is None:
            return False

        nav_offboard = (
            int(self.vehicle_status.nav_state)
            == int(VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        )
        armed = (
            int(self.vehicle_status.arming_state)
            == int(VehicleStatus.ARMING_STATE_ARMED)
        )
        return nav_offboard and armed

    def _distance_to(self, wp):
        if self.position is None:
            return math.inf

        coords = (
            float(self.position.x),
            float(self.position.y),
            float(self.position.z),
        )

        if not all(math.isfinite(v) for v in coords):
            return math.inf

        return math.sqrt(
            (coords[0] - wp["x"]) ** 2
            + (coords[1] - wp["y"]) ** 2
            + (coords[2] - wp["z"]) ** 2
        )

    def _start_land(self):
        self._vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.land_sent_at = time.monotonic()
        self.state = "LANDING"
        self._publish_status("landing")

    def _complete(self):
        self.state = "COMPLETED"
        self._publish_status("completed")

    def _fail(self, reason):
        self.state = "FAILED"
        self._publish_status("failed", reason=reason)

    def _tick(self):
        if self.state in ("IDLE", "COMPLETED", "FAILED") or not self.waypoints:
            return

        if self.state in ("PRESTREAM", "WAIT_ACTIVE", "ACTIVE"):
            self._heartbeat()
            self._setpoint(self.waypoints[self.current_index])

        if self.state == "PRESTREAM":
            self.prestream_count += 1

            # O PX4 exige um fluxo de setpoints antes de aceitar OFFBOARD.
            if self.prestream_count >= 20:
                self.activation_started_at = time.monotonic()
                self._send_activation_commands()
                self.state = "WAIT_ACTIVE"
            return

        if self.state == "WAIT_ACTIVE":
            if self._is_offboard_and_armed():
                self.state = "ACTIVE"
                self._publish_status("started")
                return

            now = time.monotonic()

            if (
                now - self.last_activation_command_at >= 2.0
                and self.activation_retries < 5
            ):
                self._send_activation_commands()

            if (
                self.activation_started_at is not None
                and now - self.activation_started_at > 12.0
            ):
                nav = (
                    int(self.vehicle_status.nav_state)
                    if self.vehicle_status is not None
                    else None
                )
                arm = (
                    int(self.vehicle_status.arming_state)
                    if self.vehicle_status is not None
                    else None
                )
                self._fail(
                    f"PX4 não entrou em OFFBOARD/ARM; nav_state={nav}, "
                    f"arming_state={arm}"
                )
            return

        if self.state == "ACTIVE":
            current = self.waypoints[self.current_index]
            distance = self._distance_to(current)

            if distance <= self.tolerance:
                if self.reached_since is None:
                    self.reached_since = time.monotonic()

                elif time.monotonic() - self.reached_since >= self.hold_seconds:
                    reached = self.current_index

                    self._publish_status(
                        "waypoint_reached",
                        waypoint=reached + 1,
                        waypoint_count=len(self.waypoints),
                        distance_m=round(distance, 3),
                    )

                    self.current_index += 1
                    self.reached_since = None

                    if self.current_index >= len(self.waypoints):
                        if self.auto_land:
                            self._start_land()
                        else:
                            self._complete()
            else:
                self.reached_since = None

            return

        if self.state == "LANDING":
            if self.vehicle_status is not None:
                disarmed = (
                    int(self.vehicle_status.arming_state)
                    == int(VehicleStatus.ARMING_STATE_DISARMED)
                )
                if disarmed:
                    self._complete()
                    return

            if self.land_sent_at and time.monotonic() - self.land_sent_at > 30.0:
                self._fail("timeout aguardando pouso/desarme")


def main(args=None):
    rclpy.init(args=args)
    node = MissionExecutor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
