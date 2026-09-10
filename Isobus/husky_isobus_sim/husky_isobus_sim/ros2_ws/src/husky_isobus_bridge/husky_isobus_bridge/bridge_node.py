from __future__ import annotations

import math
import signal
import time
from pathlib import Path
from typing import Optional

import can
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from .config import join_topic, load_yaml, parse_int
from .j1939 import build_can_id
from .protocol import (
    MOTION_UNKNOWN,
    classify_motion,
    encode_motion_vector,
    motion_state_text,
)


class HuskyVcanBridge(Node):
    """Lê /platform/odom e envia o movimento à vcan0 a cada 100 ms."""

    def __init__(self) -> None:
        super().__init__('husky_vcan_bridge')
        self.declare_parameter('config_file', '')
        config_file = str(self.get_parameter('config_file').value)
        if not config_file or not Path(config_file).is_file():
            raise RuntimeError('informe -p config_file:=/caminho/config/bridge.yaml')

        cfg = load_yaml(config_file)
        robot = cfg.get('robot', {})
        can_cfg = cfg.get('can', {})

        namespace = str(robot.get('namespace', 'a200_0000')).strip('/')
        odom_name = str(robot.get('odometry_topic', 'platform/odom'))
        self.odom_topic = join_topic(namespace, odom_name)

        self.interface = str(can_cfg.get('interface', 'vcan0'))
        self.priority = int(can_cfg.get('priority', 3))
        self.pgn = parse_int(can_cfg.get('pgn', '0xEF00'))
        self.source_address = int(can_cfg.get('source_address', 28))
        self.destination_address = int(can_cfg.get('destination_address', 255))
        self.period_s = float(can_cfg.get('period_ms', 100.0)) / 1000.0
        self.stale_timeout_s = float(can_cfg.get('stale_timeout_s', 0.5))
        self.linear_threshold = float(can_cfg.get('linear_threshold_mps', 0.02))
        self.angular_threshold = float(can_cfg.get('angular_threshold_rps', 0.05))

        if self.period_s <= 0.0 or not math.isfinite(self.period_s):
            raise ValueError('period_ms deve ser positivo')
        if self.stale_timeout_s <= 0.0 or not math.isfinite(self.stale_timeout_s):
            raise ValueError('stale_timeout_s deve ser positivo')
        if not self.interface.strip():
            raise ValueError('can.interface não pode ser vazio')
        if self.linear_threshold < 0.0 or not math.isfinite(self.linear_threshold):
            raise ValueError('linear_threshold_mps deve ser finito e não negativo')
        if self.angular_threshold < 0.0 or not math.isfinite(self.angular_threshold):
            raise ValueError('angular_threshold_rps deve ser finito e não negativo')

        self.can_id = build_can_id(
            self.priority,
            self.pgn,
            self.source_address,
            self.destination_address,
        )
        try:
            self.bus = can.Bus(interface='socketcan', channel=self.interface)
        except (can.CanError, OSError) as exc:
            raise RuntimeError(
                f'não foi possível abrir {self.interface}; '
                'crie a interface com scripts/setup_vcan.sh'
            ) from exc

        self.latest_odom: Optional[Odometry] = None
        self.latest_odom_monotonic = 0.0
        self.tx_count = 0
        self.last_state: Optional[int] = None
        self.last_status_log = 0.0

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.odom_subscription = self.create_subscription(
            Odometry,
            self.odom_topic,
            self._odom_callback,
            qos,
        )

        # Com use_sim_time=false (padrão deste nó), este timer usa tempo de parede.
        self.timer = self.create_timer(self.period_s, self._send_periodic_frame)

        self.get_logger().info(
            f'ODOM={self.odom_topic} | CAN={self.interface} | '
            f'ID=0x{self.can_id:08X} | período={self.period_s * 1000:.0f} ms'
        )
        self.get_logger().warning(
            'PGN 0xEF00 + payload 0x06 são proprietários para esta prova de conceito; '
            'não representam certificação ISO 11783.'
        )

    def _odom_callback(self, msg: Odometry) -> None:
        self.latest_odom = msg
        self.latest_odom_monotonic = time.monotonic()

    def _read_motion(self) -> tuple[float, float, bool]:
        if self.latest_odom is None:
            return math.nan, math.nan, True
        stale = (time.monotonic() - self.latest_odom_monotonic) > self.stale_timeout_s
        if stale:
            return math.nan, math.nan, True
        return (
            float(self.latest_odom.twist.twist.linear.x),
            float(self.latest_odom.twist.twist.angular.z),
            False,
        )

    def _send_periodic_frame(self) -> None:
        vx, wz, stale = self._read_motion()
        state = MOTION_UNKNOWN if stale else classify_motion(
            vx,
            wz,
            self.linear_threshold,
            self.angular_threshold,
        )
        payload = encode_motion_vector(vx, wz, state, stale)
        frame = can.Message(
            arbitration_id=self.can_id,
            data=payload,
            is_extended_id=True,
        )

        try:
            self.bus.send(frame, timeout=0.05)
        except can.CanError as exc:
            self.get_logger().error(f'falha ao enviar para {self.interface}: {exc}')
            return

        self.tx_count += 1
        now = time.monotonic()
        if state != self.last_state or now - self.last_status_log >= 5.0:
            vx_text = 'N/D' if not math.isfinite(vx) else f'{vx:+.3f} m/s'
            wz_text = 'N/D' if not math.isfinite(wz) else f'{wz:+.3f} rad/s'
            self.get_logger().info(
                f'TX #{self.tx_count} | {motion_state_text(state)} | '
                f'vx={vx_text} | wz={wz_text} | data={payload.hex(" ").upper()}'
            )
            self.last_state = state
            self.last_status_log = now

    def destroy_node(self) -> bool:
        try:
            self.bus.shutdown()
        finally:
            return super().destroy_node()


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node: Optional[HuskyVcanBridge] = None
    try:
        node = HuskyVcanBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.default_int_handler)
    main()
