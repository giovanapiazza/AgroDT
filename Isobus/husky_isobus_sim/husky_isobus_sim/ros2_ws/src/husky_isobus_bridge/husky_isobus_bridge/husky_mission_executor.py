#!/usr/bin/env python3
"""Executa missões JSON do Husky usando odometria e cmd_vel."""

import json
import math
import time

import rclpy
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String


def clamp(value, low, high):
    return max(low, min(high, value))


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class HuskyMissionExecutor(Node):
    def __init__(self):
        super().__init__("agrodt_husky_mission_executor")

        self.cmd_pub = self.create_publisher(
            TwistStamped,
            "/a200_0000/platform/cmd_vel",
            10,
        )
        self.status_pub = self.create_publisher(
            String,
            "/agrodt/husky/mission_status",
            10,
        )

        self.create_subscription(
            Odometry,
            "/a200_0000/platform/odom",
            self._odom_cb,
            10,
        )
        self.create_subscription(
            String,
            "/agrodt/husky/mission",
            self._mission_cb,
            10,
        )

        self.odom = None
        self.mission_id = None
        self.waypoints = []
        self.current_index = 0
        self.tolerance = 0.35
        self.hold_seconds = 0.4
        self.max_linear = 0.45
        self.max_angular = 0.70
        self.state = "IDLE"
        self.reached_since = None
        self.mission_started_at = None
        self.last_odom_at = None

        self.create_timer(0.05, self._tick)

        self.get_logger().info(
            "Executor do Husky pronto. Aguardando JSON em /agrodt/husky/mission"
        )

    def _odom_cb(self, msg):
        self.odom = msg
        self.last_odom_at = time.monotonic()

    def _publish_status(self, status, **extra):
        payload = {
            "mission_id": self.mission_id,
            "status": status,
            **extra,
        }
        msg = String()
        msg.data = json.dumps(payload, separators=(",", ":"))
        self.status_pub.publish(msg)
        self.get_logger().info(msg.data)

    def _publish_stop(self):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.twist.linear.x = 0.0
        msg.twist.angular.z = 0.0
        self.cmd_pub.publish(msg)

    def _mission_cb(self, msg):
        if self.state == "ACTIVE":
            self._publish_status(
                "rejected",
                reason="mission_already_running",
            )
            return

        try:
            data = json.loads(msg.data)
            payload = data.get("payload", {})

            if payload.get("command") != "start_mission":
                raise ValueError(
                    "payload.command deve ser start_mission"
                )

            raw_waypoints = payload.get("waypoints", [])
            if not raw_waypoints:
                raise ValueError(
                    "a missão não possui waypoints"
                )

            self.waypoints = [
                {
                    "x": float(wp["x"]),
                    "y": float(wp["y"]),
                }
                for wp in raw_waypoints
            ]

            self.mission_id = data.get("mission_id", 0)
            self.tolerance = float(
                payload.get("tolerance_m", 0.35)
            )
            self.hold_seconds = float(
                payload.get("hold_seconds", 0.4)
            )
            self.max_linear = float(
                payload.get("max_linear_mps", 0.45)
            )
            self.max_angular = float(
                payload.get("max_angular_rps", 0.70)
            )

            self.current_index = 0
            self.reached_since = None
            self.mission_started_at = time.monotonic()
            self.state = "ACTIVE"

            self._publish_status(
                "accepted",
                waypoint_count=len(self.waypoints),
            )
            self._publish_status("started")

        except Exception as exc:
            self._publish_stop()
            self.state = "FAILED"
            self._publish_status(
                "rejected",
                reason=str(exc),
            )

    def _pose(self):
        if self.odom is None:
            return None

        pose = self.odom.pose.pose
        return (
            float(pose.position.x),
            float(pose.position.y),
            yaw_from_quaternion(pose.orientation),
        )

    def _tick(self):
        if self.state != "ACTIVE":
            return

        if self.odom is None:
            if (
                self.mission_started_at is not None
                and time.monotonic() - self.mission_started_at > 5.0
            ):
                self._publish_stop()
                self.state = "FAILED"
                self._publish_status(
                    "failed",
                    reason="odometria indisponível",
                )
            return

        if (
            self.last_odom_at is not None
            and time.monotonic() - self.last_odom_at > 1.0
        ):
            self._publish_stop()
            self.state = "FAILED"
            self._publish_status(
                "failed",
                reason="odometria parou de atualizar",
            )
            return

        x, y, yaw = self._pose()
        target = self.waypoints[self.current_index]

        dx = target["x"] - x
        dy = target["y"] - y
        distance = math.hypot(dx, dy)

        if distance <= self.tolerance:
            self._publish_stop()

            if self.reached_since is None:
                self.reached_since = time.monotonic()
                return

            if time.monotonic() - self.reached_since < self.hold_seconds:
                return

            self._publish_status(
                "waypoint_reached",
                waypoint=self.current_index + 1,
                waypoint_count=len(self.waypoints),
                x=round(x, 3),
                y=round(y, 3),
                distance_m=round(distance, 3),
            )

            self.current_index += 1
            self.reached_since = None

            if self.current_index >= len(self.waypoints):
                self._publish_stop()
                self.state = "COMPLETED"
                self._publish_status(
                    "completed",
                    x=round(x, 3),
                    y=round(y, 3),
                )
            return

        self.reached_since = None

        target_yaw = math.atan2(dy, dx)
        yaw_error = normalize_angle(target_yaw - yaw)

        # Primeiro alinha o Husky com o waypoint. Depois avança mantendo
        # uma pequena correção angular. Isso evita curvas muito abertas.
        if abs(yaw_error) > 0.35:
            linear = 0.0
            angular = clamp(
                1.5 * yaw_error,
                -self.max_angular,
                self.max_angular,
            )
        else:
            linear = clamp(
                0.65 * distance,
                0.10,
                self.max_linear,
            )
            linear *= max(
                0.25,
                1.0 - abs(yaw_error) / 0.35,
            )
            angular = clamp(
                1.2 * yaw_error,
                -self.max_angular,
                self.max_angular,
            )

        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.twist.linear.x = float(linear)
        cmd.twist.angular.z = float(angular)
        self.cmd_pub.publish(cmd)

    def destroy_node(self):
        self._publish_stop()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = HuskyMissionExecutor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
