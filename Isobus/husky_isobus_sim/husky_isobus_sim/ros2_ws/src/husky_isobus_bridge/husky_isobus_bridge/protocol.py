from __future__ import annotations

import math
import struct
from dataclasses import dataclass

PROTOCOL_VERSION = 1
TYPE_MOTION_VECTOR = 0x06
INT16_NA = -32768

MOTION_STOPPED = 0
MOTION_FORWARD = 1
MOTION_REVERSE = 2
MOTION_LEFT = 3
MOTION_RIGHT = 4
MOTION_FORWARD_LEFT = 5
MOTION_FORWARD_RIGHT = 6
MOTION_REVERSE_LEFT = 7
MOTION_REVERSE_RIGHT = 8
MOTION_UNKNOWN = 0xFF

VALID_STATES = {
    MOTION_STOPPED,
    MOTION_FORWARD,
    MOTION_REVERSE,
    MOTION_LEFT,
    MOTION_RIGHT,
    MOTION_FORWARD_LEFT,
    MOTION_FORWARD_RIGHT,
    MOTION_REVERSE_LEFT,
    MOTION_REVERSE_RIGHT,
    MOTION_UNKNOWN,
}


@dataclass(frozen=True)
class MotionFrame:
    linear_x_mps: float
    angular_z_rps: float
    motion_state: int
    stale: bool


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _scaled_int16(value: float, scale: float) -> int:
    if not _finite(value):
        return INT16_NA
    raw = int(round(float(value) / scale))
    if raw <= INT16_NA or raw > 32767:
        raise OverflowError(f'valor {value} fora do intervalo do payload')
    return raw


def classify_motion(
    linear_x_mps: float,
    angular_z_rps: float,
    linear_threshold_mps: float = 0.02,
    angular_threshold_rps: float = 0.05,
) -> int:
    """Classifica o movimento usando a convenção ROS: +x frente, +z esquerda."""
    if not (_finite(linear_x_mps) and _finite(angular_z_rps)):
        return MOTION_UNKNOWN

    vx = 0.0 if abs(linear_x_mps) < linear_threshold_mps else float(linear_x_mps)
    wz = 0.0 if abs(angular_z_rps) < angular_threshold_rps else float(angular_z_rps)

    if vx == 0.0 and wz == 0.0:
        return MOTION_STOPPED
    if vx == 0.0:
        return MOTION_LEFT if wz > 0.0 else MOTION_RIGHT
    if wz == 0.0:
        return MOTION_FORWARD if vx > 0.0 else MOTION_REVERSE
    if vx > 0.0:
        return MOTION_FORWARD_LEFT if wz > 0.0 else MOTION_FORWARD_RIGHT
    return MOTION_REVERSE_LEFT if wz > 0.0 else MOTION_REVERSE_RIGHT


def motion_state_text(state: int) -> str:
    return {
        MOTION_STOPPED: 'PARADO',
        MOTION_FORWARD: 'FRENTE',
        MOTION_REVERSE: 'RÉ',
        MOTION_LEFT: 'ESQUERDA',
        MOTION_RIGHT: 'DIREITA',
        MOTION_FORWARD_LEFT: 'FRENTE + ESQUERDA',
        MOTION_FORWARD_RIGHT: 'FRENTE + DIREITA',
        MOTION_REVERSE_LEFT: 'RÉ + ESQUERDA',
        MOTION_REVERSE_RIGHT: 'RÉ + DIREITA',
        MOTION_UNKNOWN: 'N/D',
    }.get(state, f'DESCONHECIDO({state})')


def encode_motion_vector(
    linear_x_mps: float,
    angular_z_rps: float,
    motion_state: int,
    stale: bool,
) -> bytes:
    """Codifica o único payload usado pela versão limpa.

    Byte 0     versão = 0x01
    Byte 1     tipo = 0x06
    Bytes 2-3  linear.x, int16 LE, 0.001 m/s/bit
    Bytes 4-5  angular.z, int16 LE, 0.001 rad/s/bit
    Byte 6     estado de movimento
    Byte 7     flags: bit1 = odometria stale
    """
    if stale:
        linear_x_mps = math.nan
        angular_z_rps = math.nan
        motion_state = MOTION_UNKNOWN

    if motion_state not in VALID_STATES:
        motion_state = MOTION_UNKNOWN

    flags = 0x02 if stale else 0x00
    return struct.pack(
        '<BBhhBB',
        PROTOCOL_VERSION,
        TYPE_MOTION_VECTOR,
        _scaled_int16(linear_x_mps, 0.001),
        _scaled_int16(angular_z_rps, 0.001),
        motion_state,
        flags,
    )


def decode_motion_vector(payload: bytes) -> MotionFrame:
    if len(payload) != 8:
        raise ValueError('payload deve ter exatamente 8 bytes')
    version, msg_type, vx_raw, wz_raw, state, flags = struct.unpack('<BBhhBB', payload)
    if version != PROTOCOL_VERSION:
        raise ValueError(f'versão de protocolo não suportada: {version}')
    if msg_type != TYPE_MOTION_VECTOR:
        raise ValueError(f'tipo esperado 0x06, recebido 0x{msg_type:02X}')

    vx = math.nan if vx_raw == INT16_NA else vx_raw * 0.001
    wz = math.nan if wz_raw == INT16_NA else wz_raw * 0.001
    return MotionFrame(vx, wz, state, bool(flags & 0x02))
