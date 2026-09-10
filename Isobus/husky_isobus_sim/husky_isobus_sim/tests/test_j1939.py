import pytest

from husky_isobus_bridge.j1939 import build_can_id, parse_can_id


def test_proprietary_a_broadcast_id():
    can_id = build_can_id(3, 0xEF00, 0x1C, 0xFF)
    assert can_id == 0x0CEFFF1C
    fields = parse_can_id(can_id)
    assert fields.priority == 3
    assert fields.pgn == 0xEF00
    assert fields.source_address == 0x1C
    assert fields.destination_address == 0xFF


def test_pdu1_rejects_destination_encoded_inside_pgn():
    with pytest.raises(ValueError, match='PDU1'):
        build_can_id(3, 0xEFFF, 0x1C, 0x80)
