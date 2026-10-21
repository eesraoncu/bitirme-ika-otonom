"""Demo panelinin metinleri ve harita dönüşümü (panel_text.py).

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


@pytest.mark.parametrize("v, nd, s", [(14.5, 1, "14,5"), (10.0, 1, "10"), (0.0, 1, "0"),
                                      (-0.04, 1, "0"), (0.3, 2, "0,3"), (-6.0, 1, "-6")])
def test_num(v, nd, s):
    assert pt.num(v, nd) == s


def test_task_lines():
    assert pt.task_line({"cmd": "git", "x": 14.5, "y": 0.0}) == "git → (14,5; 0)"
    assert pt.task_line({"cmd": "git", "x": 10.0, "y": 0.0, "yer": "kazi_bati"}) == "git → kazi_bati (10; 0)"
    assert pt.task_line({"cmd": "bekle", "sure_s": 20.0}) == "bekle 20 s"
    assert pt.task_line({"cmd": "hiz_siniri", "deger_mps": 2.0}) == "hız sınırı 2 m/s"
    assert pt.task_line({"cmd": "dur"}) == "dur"


def test_feedback_line_shows_rule_to_audience():
    ok = pt.feedback_line({"accepted": True, "text": "Komut kabul edildi."})
    assert ok == ("✓ KABUL", "kabul")
    # C: ajan yalnız "Komut reddedildi." görür, izleyici kuralı da görür
    text, kind = pt.feedback_line({"accepted": False, "text": "Komut reddedildi."},
                                  {"result": "REJECTED", "rule": "GEOFENCE"})
    assert (text, kind) == ("✗ RET · GEOFENCE — Komut reddedildi.", "ret")
    text, _ = pt.feedback_line({"accepted": False, "text": "Nav2 hazır değil."})
    assert text == "✗ RET — Nav2 hazır değil."                # kart kararı yoksa kural yok


def test_is_rejection():
    assert pt.is_rejection({"result": "REJECTED"})
    assert not pt.is_rejection({"result": "ACCEPTED"})


def test_log_lines():
    assert pt.log_line({"event": "görev", "text": "Kapı önüne git"}) == ("Görev: “Kapı önüne git”", "gorev")
    # karta giden adım panelde /guard/task'tan gösterilir: tekrar yazılmaz
    assert pt.log_line({"event": "adım", "task": {"cmd": "git"}, "tool": "git"}) is None
    assert pt.log_line({"event": "adım", "task": None, "tool": "git", "result": "Karta gönderilmedi."}) \
        == ("Geçersiz çağrı (git) — Karta gönderilmedi.", "gecersiz")
    assert pt.log_line({"event": "vazgeçti", "rejections": 3}) == ("Ajan vazgeçti (3 ret)", "son")
    assert pt.log_line({"event": "ayarlar"}) is None


def test_badge():
    assert pt.badge(None, None)[1] == "KART YOK"
    assert pt.badge({"state": "NORMAL"}, 0.5)[1] == "NORMAL"
    assert pt.badge({"state": "HOLD"}, 0.5)[1].startswith("HOLD")
    assert pt.badge({"state": "NORMAL"}, pt.STATUS_STALE_S + 0.1)[1] == "BAĞLANTI YOK"   # kablo çekildi


def test_world_to_px():
    o, r, h = (-4.38, -12.0), 0.05, 454
    assert pt.world_to_px(0.0, 0.0, o, r, h) == pytest.approx((87.6, 214.0))
    assert pt.world_to_px(-4.38, -12.0, o, r, h) == pytest.approx((0.0, 454.0))   # origin: sol alt
    x1, y1 = pt.world_to_px(0.0, 1.0, o, r, h)
    assert y1 == pytest.approx(194.0)                          # kuzey (y+) görüntüde yukarı
