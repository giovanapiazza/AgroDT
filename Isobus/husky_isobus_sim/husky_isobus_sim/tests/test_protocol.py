import math

from husky_isobus_bridge.protocol import (
    MOTION_FORWARD,
    MOTION_LEFT,
    MOTION_REVERSE,
    MOTION_RIGHT,
    MOTION_STOPPED,
    MOTION_UNKNOWN,
    classify_motion,
    decode_motion_vector,
    encode_motion_vector,
)


def test_classification():
    assert classify_motion(0.0, 0.0) == MOTION_STOPPED
    assert classify_motion(1.0, 0.0) == MOTION_FORWARD
    assert classify_motion(-1.0, 0.0) == MOTION_REVERSE
    assert classify_motion(0.0, 0.5) == MOTION_LEFT
    assert classify_motion(0.0, -0.5) == MOTION_RIGHT


def test_known_payloads():
    assert encode_motion_vector(1.0, 0.0, MOTION_FORWARD, False).hex() == '0106e80300000100'
    assert encode_motion_vector(-1.0, 0.0, MOTION_REVERSE, False).hex() == '010618fc00000200'
    assert encode_motion_vector(0.0, 0.5, MOTION_LEFT, False).hex() == '01060000f4010300'
    assert encode_motion_vector(0.0, -0.5, MOTION_RIGHT, False).hex() == '010600000cfe0400'


def test_stale_payload():
    payload = encode_motion_vector(math.nan, math.nan, MOTION_UNKNOWN, True)
    assert payload.hex() == '010600800080ff02'
    decoded = decode_motion_vector(payload)
    assert decoded.stale is True
    assert math.isnan(decoded.linear_x_mps)
    assert math.isnan(decoded.angular_z_rps)
