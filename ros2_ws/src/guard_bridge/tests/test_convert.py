"""Köprünün birim çevirileri (convert.py) doğru mu.

    python3 -m pytest ros2_ws/src/guard_bridge/tests -v

Sınanan: yuvarlama, int16 kırpma, NaN/sonsuz, açı sarma, dördey ↔ yön açısı
gidiş-dönüş, VERDICT metni.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import convert as cv  # noqa: E402


def test_to_int16_rounds_to_nearest():
    assert cv.to_int16(0.3004, 1000) == 300
    assert cv.to_int16(0.3006, 1000) == 301
    assert cv.to_int16(-0.0126, 1000) == -13


@pytest.mark.parametrize("value, expected", [(40.0, 32767), (-40.0, -32768)])
def test_to_int16_clamps(value, expected):
    assert cv.to_int16(value, 1000) == expected


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_to_int16_non_finite_is_zero(value):
    assert cv.to_int16(value, 1000) == 0


@pytest.mark.parametrize("a, expected", [
    (0.0, 0.0), (math.pi / 2, math.pi / 2), (3 * math.pi / 2, -math.pi / 2),
    (-3 * math.pi / 2, math.pi / 2), (math.pi, -math.pi), (7 * math.pi, -math.pi),
])
def test_wrap_angle(a, expected):
    assert cv.wrap_angle(a) == pytest.approx(expected)


@pytest.mark.parametrize("yaw_mrad", [0, 1571, -1571, 3141, -3141, 500, -2500])
def test_pose_round_trip(yaw_mrad):
    x, y, qz, qw = cv.cm_to_pose(800, -250, yaw_mrad)
    assert (x, y) == (8.0, -2.5)
    assert cv.pose_to_cm(x, y, 0.0, 0.0, qz, qw) == (800, -250, yaw_mrad)


def test_pose_north_facing():
    # Kuzeye bakan (yaw = π/2) dördey: qz = qw = √2/2
    s = math.sqrt(2) / 2
    assert cv.pose_to_cm(8.0, 2.0, 0.0, 0.0, s, s) == (800, 200, 1571)


def test_pose_negated_quaternion_is_same_yaw():
    # q ve −q aynı dönüştür
    x, y, qz, qw = cv.cm_to_pose(0, 0, 1000)
    assert cv.pose_to_cm(0, 0, 0.0, 0.0, -qz, -qw) == (0, 0, 1000)


def test_pose_outside_int16_is_clamped():
    assert cv.pose_to_cm(500.0, -500.0, 0, 0, 0, 1)[:2] == (32767, -32768)


def test_twist_round_trip():
    assert cv.twist_to_cmd(0.3, 0.1) == (300, 100)
    assert cv.cmd_to_twist(300, 100) == (0.3, 0.1)
    assert cv.twist_to_cmd(-0.5, -0.6) == (-500, -600)


def test_twist_nan_is_stop():
    assert cv.twist_to_cmd(math.nan, 0.2) == (0, 200)


def test_verdict_text():
    d = json.loads(cv.verdict_text(12, "REJECTED", "GEOFENCE", "GOAL_IN_FORBIDDEN",
                                   0, 0, 0, 800, 200))
    assert d == {"ref_seq": 12, "result": "REJECTED", "rule": "GEOFENCE",
                 "reason": "GOAL_IN_FORBIDDEN", "value": 0, "lo": 0, "hi": 0,
                 "hint_m": [8.0, 2.0]}
