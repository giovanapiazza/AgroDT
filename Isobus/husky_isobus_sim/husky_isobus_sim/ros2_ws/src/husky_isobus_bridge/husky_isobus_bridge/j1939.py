from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdentifierFields:
    priority: int
    pgn: int
    source_address: int
    destination_address: int | None


def build_can_id(
    priority: int,
    pgn: int,
    source_address: int,
    destination_address: int = 0xFF,
) -> int:
    """Monta um identificador CAN estendido de 29 bits no formato J1939."""
    if not 0 <= priority <= 7:
        raise ValueError('priority deve estar entre 0 e 7')
    if not 0 <= source_address <= 0xFF:
        raise ValueError('source_address deve estar entre 0 e 255')
    if not 0 <= destination_address <= 0xFF:
        raise ValueError('destination_address deve estar entre 0 e 255')
    if not 0 <= pgn <= 0x3FFFF:
        raise ValueError('PGN deve estar entre 0 e 0x3FFFF')

    edp = (pgn >> 17) & 0x01
    dp = (pgn >> 16) & 0x01
    pf = (pgn >> 8) & 0xFF
    if pf < 240 and (pgn & 0xFF) != 0:
        raise ValueError(
            'PGN PDU1 deve ter o byte menos significativo igual a zero; '
            'use destination_address para informar o destino'
        )
    ps = destination_address if pf < 240 else (pgn & 0xFF)

    return (
        (priority << 26)
        | (edp << 25)
        | (dp << 24)
        | (pf << 16)
        | (ps << 8)
        | source_address
    )


def parse_can_id(can_id: int) -> IdentifierFields:
    can_id &= 0x1FFFFFFF
    priority = (can_id >> 26) & 0x07
    edp = (can_id >> 25) & 0x01
    dp = (can_id >> 24) & 0x01
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    source_address = can_id & 0xFF

    if pf < 240:
        pgn = (edp << 17) | (dp << 16) | (pf << 8)
        destination_address = ps
    else:
        pgn = (edp << 17) | (dp << 16) | (pf << 8) | ps
        destination_address = None

    return IdentifierFields(priority, pgn, source_address, destination_address)
