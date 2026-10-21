"""Demo panelinin metinleri, durumları ve küçük hesapları (panel_text.py).

    python3 -m pytest ros2_ws/src/demo_panel/tests -v

Harita dönüşümü elle: ika_saha haritası origin (−4,38; −12), 0,05 m/piksel, 454 satır.
Başlangıç (0; 0) → x = 4,38 / 0,05 = 87,6; y = 454 − 12 / 0,05 = 214.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import panel_text as pt  # noqa: E402

LIMITS_H = Path(__file__).resolve().parents[4] / "firmware" / "app" / "rules" / "limits" / "limits.h"


@pytest.mark.parametrize("v, nd, s", [(14.5, 1, "14,5"), (10.0, 1, "10"), (0.0, 1, "0"),
                                      (-0.04, 1, "0"), (0.3, 2, "0,3"), (-6.0, 1, "-6")])
def test_num(v, nd, s):
    assert pt.num(v, nd) == s


def test_task_bubbles():
    assert pt.task_bubble({"cmd": "git", "x": 14.5, "y": 0.0}) == ("komut", "Ajan → kart", "git → (14,5; 0)")
    assert pt.task_line({"cmd": "git", "x": 10.0, "y": 0.0, "yer": "kazi_bati"}) == "git → kazi_bati (10; 0)"
    assert pt.task_line({"cmd": "bekle", "sure_s": 20.0}) == "bekle 20 s"
    assert pt.task_line({"cmd": "hiz_siniri", "deger_mps": 2.0}) == "hız sınırı 2 m/s"
    assert pt.task_line({"cmd": "dur"}) == "dur"


def test_feedback_bubble_shows_rule_to_audience():
    assert pt.feedback_bubble({"accepted": True, "text": "Komut kabul edildi."}) \
        == ("kabul", "Kart · KABUL", "Komut kabul edildi.")
    # C: ajan yalnız "Komut reddedildi." görür, izleyici kuralı başlıkta görür
    assert pt.feedback_bubble({"accepted": False, "text": "Komut reddedildi."},
                              {"result": "REJECTED", "rule": "GEOFENCE"}) \
        == ("ret", "Kart · RET · GEOFENCE", "Komut reddedildi.")
    assert pt.feedback_bubble({"accepted": False, "text": "Nav2 hazır değil."}) \
        == ("ret", "Kart · RET", "Nav2 hazır değil.")          # kart kararı yoksa kural yok


def test_is_rejection():
    assert pt.is_rejection({"result": "REJECTED"})
    assert not pt.is_rejection({"result": "ACCEPTED"})


def test_log_bubbles():
    assert pt.log_bubble({"event": "görev", "text": "Kapı önüne git"}) == ("gorev", "Operatör", "Kapı önüne git")
    # karta giden adım panelde /guard/task'tan gösterilir: tekrar yazılmaz
    assert pt.log_bubble({"event": "adım", "task": {"cmd": "git"}, "tool": "git"}) is None
    assert pt.log_bubble({"event": "adım", "task": None, "tool": "git", "result": "Karta gönderilmedi."}) \
        == ("gecersiz", "Ajan · geçersiz çağrı (git)", "Karta gönderilmedi.")
    assert pt.log_bubble({"event": "vazgeçti", "rejections": 3})[:2] == ("son", "Ajan · vazgeçti")
    assert pt.log_bubble({"event": "ayarlar"}) is None


def test_badge():
    assert pt.badge(None, None)[1] == "KART YOK"
    assert pt.badge({"state": "NORMAL"}, 0.5) == ("green", "NORMAL")
    assert pt.badge({"state": "HOLD"}, 0.5) == ("red", "HOLD")
    assert pt.badge({"state": "NORMAL"}, pt.STATUS_STALE_S + 0.1)[1] == "BAĞLANTI YOK"   # kablo çekildi
    assert all(text in pt.BADGE_HINT for _, text in pt.BADGE.values())


def test_light():
    assert pt.light(None) == "none"
    assert pt.light(0.3) == "ok"
    assert pt.light(pt.LIVE_STALE_S + 0.1) == "stale"


def test_ring():
    assert pt.ring(0.0, 2.0) == (0.0, 1.0)
    assert pt.ring(1.0, 2.0) == (0.5, 0.5)
    assert pt.ring(2.5, 2.0) is None and pt.ring(-0.1, 2.0) is None


def test_gauge_and_clock():
    assert pt.gauge_fraction(0.375, 0.75) == 0.5
    assert pt.gauge_fraction(-0.375, 0.75) == 0.5                # geri gitme
    assert pt.gauge_fraction(2.0, 0.75) == 1.0
    assert pt.clock(134.7) == "02:14" and pt.clock(-1) == "00:00"


def test_config_label():
    assert pt.config_label("D") == "D · kart, gerekçeli"
    assert pt.config_label("") == ""


def test_speed_limit_from_header():
    assert pt.speed_limit_from_header("#define LIMIT_V_MAX_MM_S    600   /* ... */") == 0.6
    assert pt.speed_limit_from_header("yok") is None
    assert pt.speed_limit_from_header(LIMITS_H.read_text()) == 0.6   # kartın gerçek değeri (RULES §1)


def test_world_to_px():
    o, r, h = (-4.38, -12.0), 0.05, 454
    assert pt.world_to_px(0.0, 0.0, o, r, h) == pytest.approx((87.6, 214.0))
    assert pt.world_to_px(-4.38, -12.0, o, r, h) == pytest.approx((0.0, 454.0))   # origin: sol alt
    assert pt.world_to_px(0.0, 1.0, o, r, h)[1] == pytest.approx(194.0)           # kuzey yukarı


SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def test_overlap():
    assert pt._overlap(SQUARE, [(0.5, 0.5), (2, 0.5), (2, 2), (0.5, 2)])          # iç içe geçiyor
    assert not pt._overlap(SQUARE, [(2, 0), (3, 0), (3, 1), (2, 1)])              # yan yana, ayrık
    assert pt._overlap(SQUARE, [(1, 0), (2, 0), (2, 1), (1, 1)])                  # değmek çakışmadır
    # merkez (1,4; 1,4), yarıçap 0,7 eşkenar dörtgen: dış kutuları kesişir ama şekiller değmez
    # (karenin (1; 1) köşesi: |−0,4| + |−0,4| = 0,8 > 0,7). Yalnız eksenlere bakan test bunu kaçırır.
    diamond = [(2.1, 1.4), (1.4, 2.1), (0.7, 1.4), (1.4, 0.7)]
    assert not pt._overlap(SQUARE, diamond)


def test_label_side():
    boxes = [("right", (12, -6, 52, 6)), ("left", (-52, -6, -12, 6)),
             ("above", (-20, -24, 20, -12)), ("below", (-20, 12, 20, 24))]
    assert pt.label_side(boxes, None) == "right"                                 # araç yok
    assert pt.label_side(boxes, [(100, 100), (110, 100), (110, 110), (100, 110)]) == "right"   # uzakta
    right_only = [(10, -8), (60, -8), (60, 8), (10, 8)]                          # sağdaki etiketi örter
    assert pt.label_side(boxes, right_only) == "left"
    # araç noktanın üstünde, doğuya bakıyor: sağı ve solu örter, üst ve alt boş
    assert pt.label_side(boxes, [(-60, -8), (60, -8), (60, 8), (-60, 8)]) == "above"
    everywhere = [(-100, -100), (100, -100), (100, 100), (-100, 100)]
    assert pt.label_side(boxes, everywhere) == "right"                           # hepsi örtülü: ilk aday
