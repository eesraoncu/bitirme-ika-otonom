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


# ---- Görev arayüzü (Faz 4.2) --------------------------------------------------------

BELIEF = {"x": 1.5, "y": -0.25, "stamp": 100.0}
SAFE = {"baslangic": (0, 0), "konteyner_onu": (850, 100)}


def _task(**kw):
    return json.dumps(kw)


def test_parse_task_git():
    t = cv.parse_task(_task(id="g1", cmd="git", x=8.5, y=1.0, yaw=0.5, belief=BELIEF))
    assert (t["cmd"], t["x"], t["y"], t["yaw"], t["belief"]) == ("git", 8.5, 1.0, 0.5, BELIEF)


def test_parse_task_dur_needs_no_belief():
    assert cv.parse_task(_task(id="s", cmd="dur")) == {"id": "s", "cmd": "dur"}


@pytest.mark.parametrize("text,what", [
    ("{bozuk", "JSON değil"),
    ("[1, 2]", "nesnesi"),
    (_task(id="1", cmd="uc"), "'cmd'"),
    (_task(id="1", cmd="git", x="8", y=1, belief=BELIEF), "'x' sayı"),
    (_task(id="1", cmd="git", x=8, y=True, belief=BELIEF), "'y' sayı"),
    (_task(id="1", cmd="git", x=8, y=1), "'belief'"),
    (_task(id="1", cmd="bekle", sure_s=0, belief=BELIEF), "'sure_s'"),
    (_task(id="1", cmd="bekle", sure_s=70000, belief=BELIEF), "'sure_s'"),
    (_task(id="1", cmd="hiz_siniri", belief=BELIEF), "'deger_mps'"),
    (_task(id="1", cmd="bekle", sure_s=5, belief={"x": 0, "y": 0}), "'stamp'"),
])
def test_parse_task_rejects(text, what):
    with pytest.raises(cv.TaskError, match=what):
        cv.parse_task(text)


def test_parse_task_rejects_nan_json():
    # Python'un json'u NaN'ı kabul eder: sayı denetimi yakalamalı
    with pytest.raises(cv.TaskError, match="'x' sayı"):
        cv.parse_task('{"id": "1", "cmd": "git", "x": NaN, "y": 0, "belief": {"x": 0, "y": 0, "stamp": 0}}')


@pytest.mark.parametrize("stamp,now,board,expected", [
    (99.5, 100.0, 50_000, 49_500),                # 500 ms önce okunmuş
    (100.0, 100.0, 50_000, 50_000),
    (99.0, 100.0, 300, (300 - 1000) & 0xFFFFFFFF),  # kartın saati yeni başlamış: sarar
])
def test_ros_to_board_ms(stamp, now, board, expected):
    assert cv.ros_to_board_ms(stamp, now, board) == expected


def test_task_args_each_command():
    b = BELIEF
    assert cv.task_args(cv.parse_task(_task(id="1", cmd="git", x=8.5, y=1.0, yaw=7.0, belief=b)), 42) \
        == ("git", 850, 100, round(cv.wrap_angle(7.0) * 1000), 150, -25, 42)
    assert cv.task_args(cv.parse_task(_task(id="1", cmd="bekle", sure_s=29.6, belief=b)), 42) \
        == ("bekle", 30, 150, -25, 42)
    assert cv.task_args(cv.parse_task(_task(id="1", cmd="hiz_siniri", deger_mps=0.3, belief=b)), 42) \
        == ("hiz_siniri", 300, 150, -25, 42)
    # limit dışı istek kırpılmadan gider (LIMIT'i kart denetler); negatif 0 olur (NOT_POSITIVE)
    assert cv.task_args(cv.parse_task(_task(id="1", cmd="hiz_siniri", deger_mps=2.0, belief=b)), 42)[1] == 2000
    assert cv.task_args(cv.parse_task(_task(id="1", cmd="hiz_siniri", deger_mps=-1, belief=b)), 42)[1] == 0
    assert cv.task_args(cv.parse_task(_task(id="1", cmd="dur")), 42) == ("dur",)


def test_safe_point_name():
    assert cv.safe_point_name(850, 100, SAFE) == "konteyner_onu"
    assert cv.safe_point_name(851, 100, SAFE) is None


def _fb(reason, value=0, lo=0, hi=0, hx=0, hy=0, rule="X", full=True):
    return cv.feedback_text("REJECTED", rule, reason, value, lo, hi, hx, hy, full=full, safe_points=SAFE)


def test_feedback_accepted_and_minimal():
    assert cv.feedback_text("ACCEPTED", "NONE", "NONE", 0, 0, 0, 0, 0, full=True) == "Komut kabul edildi."
    assert _fb("TOO_FAR", 310, 0, 145, 420, 150, full=False) == "Komut reddedildi."   # C: gerekçe gizli


def test_feedback_geofence_names_safe_point():
    t = _fb("GOAL_IN_FORBIDDEN", hx=850, hy=100, rule="GEOFENCE")
    assert t == ("Komut reddedildi (GEOFENCE / GOAL_IN_FORBIDDEN). Hedef yasak bölgede. "
                 "En yakın güvenli nokta: konteyner_onu (8,50; 1,00).")
    assert "(26,00; 0,00)" in _fb("GOAL_OUTSIDE_ALLOWED", hx=2600, hy=0)       # adsız nokta


def test_feedback_too_far_matches_protocol_example():
    # protocol §7.3'teki örnek
    t = _fb("TOO_FAR", 310, 0, 145, 420, 150, rule="CONSISTENCY")
    assert t == ("Komut reddedildi (CONSISTENCY / TOO_FAR). Varsaydığın konum telemetriden "
                 "3,10 m uzak, tolerans 1,45 m. Aracın şu anki konumu: (4,20; 1,50).")


@pytest.mark.parametrize("reason,args,piece", [
    ("ABOVE_MAX", (2000, 1, 600), "2 m/s, izinli aralık 0,001–0,6 m/s"),
    ("NOT_POSITIVE", (0, 1, 600), "0'dan büyük olmalı"),
    ("BELIEF_TOO_OLD", (6009, 0, 5000), "6,0 s eski, en çok 5 s"),
    ("BELIEF_FROM_FUTURE", (-120, -50, 0), "120 ms ileride"),
    ("NO_TELEMETRY", (754, 0, 500), "754 ms'dir"),
    ("TOO_OLD", (507, -50, 200), "507 ms'de ulaştı, en çok 200 ms"),
    ("FROM_FUTURE", (-192, -50, 200), "192 ms ileride (en çok 50 ms)"),
    ("IN_HOLD", (0, 0, 0), "HOLD"),
    ("IN_RECOVERY", (0, 0, 0), "RECOVERY"),
])
def test_feedback_each_reason(reason, args, piece):
    assert piece in _fb(reason, *args)


@pytest.mark.parametrize("text,expected", [
    ('{"id": "g9", "cmd": "uc"}', "g9"), ("{bozuk", ""), ("[1]", ""), ('{"cmd": "git"}', ""),
])
def test_task_id_of_bad_task(text, expected):
    assert cv.task_id(text) == expected
