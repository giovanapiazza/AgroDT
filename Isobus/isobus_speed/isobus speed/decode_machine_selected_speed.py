#!/usr/bin/env python3
"""Decodifica os 8 bytes do PGN 61474 (0xF022), Machine Selected Speed."""

from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable, List

DIRECTIONS = {
    0: "Reverse",
    1: "Forward",
    2: "Error",
    3: "Not Available",
}

SPEED_SOURCES = {
    0: "Wheel Based Speed",
    1: "Ground Based Speed",
    2: "Navigation Based Speed",
    3: "Blended",
    4: "Simulated",
    5: "Reserved",
    6: "Reserved",
    7: "Not Available",
}

LIMIT_STATUS = {
    0: "Not Limited",
    1: "Operator Limited/Controlled",
    2: "Limited High",
    3: "Limited Low",
    4: "Reserved",
    5: "Reserved",
    6: "Non-recoverable Fault",
    7: "Not Available",
}


def parse_bytes(values: Iterable[str]) -> List[int]:
    joined = " ".join(values).strip()
    tokens = re.findall(r"(?i)(?<![0-9a-f])[0-9a-f]{2}(?![0-9a-f])", joined)

    if len(tokens) != 8:
        compact = re.sub(r"[^0-9a-fA-F]", "", joined)
        if len(compact) == 16:
            tokens = [compact[index:index + 2] for index in range(0, 16, 2)]

    if len(tokens) != 8:
        raise ValueError("informe exatamente 8 bytes hexadecimais")

    return [int(token, 16) for token in tokens]


def decode(data: List[int]) -> dict:
    speed_mmps = data[0] | (data[1] << 8)
    distance_mm = (
        data[2]
        | (data[3] << 8)
        | (data[4] << 16)
        | (data[5] << 24)
    )
    exit_reason = data[6] & 0x3F
    direction = data[7] & 0x03
    speed_source = (data[7] >> 2) & 0x07
    limit_status = (data[7] >> 5) & 0x07

    return {
        "speed_mmps": speed_mmps,
        "speed_kmh": speed_mmps * 3.6 / 1000.0,
        "distance_mm": distance_mm,
        "distance_m": distance_mm / 1000.0,
        "exit_reason": exit_reason,
        "direction": DIRECTIONS[direction],
        "speed_source": SPEED_SOURCES[speed_source],
        "limit_status": LIMIT_STATUS[limit_status],
        "reserved_bits_ok": (data[6] & 0xC0) == 0xC0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decodifica os 8 bytes do PGN ISOBUS 61474 / 0xF022."
    )
    parser.add_argument(
        "bytes",
        nargs="+",
        help="Exemplo: AE 08 A0 86 01 00 C0 11",
    )
    args = parser.parse_args()

    try:
        data = parse_bytes(args.bytes)
    except ValueError as error:
        parser.error(str(error))

    result = decode(data)
    print("PGN 61474 / 0xF022 - Machine Selected Speed")
    print("Bytes              : " + " ".join(f"{value:02X}" for value in data))
    print(f"Velocidade         : {result['speed_mmps']} mm/s ({result['speed_kmh']:.3f} km/h)")
    print(f"Distancia          : {result['distance_mm']} mm ({result['distance_m']:.3f} m)")
    print(f"Exit reason        : {result['exit_reason']}")
    print(f"Direcao            : {result['direction']}")
    print(f"Fonte              : {result['speed_source']}")
    print(f"Limit status       : {result['limit_status']}")
    print("Bits reservados B7 : " + ("corretos (11b)" if result["reserved_bits_ok"] else "incorretos"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
