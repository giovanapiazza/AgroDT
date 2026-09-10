from __future__ import annotations

import argparse
import math
import sys
import time

import can

from .config import load_yaml, parse_int
from .j1939 import parse_can_id
from .protocol import TYPE_MOTION_VECTOR, decode_motion_vector, motion_state_text


def fmt(value: float, unit: str) -> str:
    return 'N/D' if not math.isfinite(value) else f'{value:+.3f} {unit}'


def main() -> None:
    parser = argparse.ArgumentParser(description='Monitor do movimento recebido da vcan0.')
    parser.add_argument('--config', required=True, help='Caminho para config/bridge.yaml')
    args = parser.parse_args()

    cfg = load_yaml(args.config).get('can', {})
    interface = str(cfg.get('interface', 'vcan0'))
    expected_pgn = parse_int(cfg.get('pgn', '0xEF00'))

    bus = can.Bus(interface='socketcan', channel=interface)
    last_rx_mono = 0.0
    frame_count = 0

    try:
        while True:
            frame = bus.recv(timeout=1.0)
            if frame is None:
                print(f'[{interface}] aguardando frames...', flush=True)
                continue
            if not frame.is_extended_id or len(frame.data) != 8:
                continue

            fields = parse_can_id(frame.arbitration_id)
            if fields.pgn != expected_pgn or frame.data[1] != TYPE_MOTION_VECTOR:
                continue

            try:
                decoded = decode_motion_vector(bytes(frame.data))
            except ValueError as exc:
                print(
                    f'[{interface}] quadro ignorado: {exc} | '
                    f'{bytes(frame.data).hex(" ").upper()}',
                    file=sys.stderr,
                    flush=True,
                )
                continue
            now = time.monotonic()
            delta_ms = math.nan if last_rx_mono == 0.0 else (now - last_rx_mono) * 1000.0
            last_rx_mono = now
            frame_count += 1

            lines = [
                'HUSKY -> vcan0 | MOVIMENTO DECODIFICADO DO CAN',
                '=' * 66,
                f'Frames     : {frame_count}',
                f'CAN ID     : 0x{frame.arbitration_id:08X}',
                f'PGN        : 0x{fields.pgn:05X}',
                f'Intervalo  : {"N/D" if not math.isfinite(delta_ms) else f"{delta_ms:.1f} ms"}',
                f'Movimento  : {motion_state_text(decoded.motion_state)}',
                f'linear.x   : {fmt(decoded.linear_x_mps, "m/s")}',
                f'angular.z  : {fmt(decoded.angular_z_rps, "rad/s")}',
                f'Odom stale : {"SIM" if decoded.stale else "não"}',
                f'Payload    : {bytes(frame.data).hex(" ").upper()}',
                '',
                'Este monitor lê somente a vcan0; não lê /odom.',
                'Ctrl+C para sair.',
            ]

            if sys.stdout.isatty():
                sys.stdout.write('\033[2J\033[H' + '\n'.join(lines) + '\n')
                sys.stdout.flush()
            else:
                print(' | '.join(lines[2:11]), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()
