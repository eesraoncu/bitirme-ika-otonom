"""Haritanın sınıflanması ve lidar noktaları (map_style.py).

    python3 -m pytest ros2_ws/src/demo_panel/tests -v

Eşikler ika_saha.yaml'daki gibi: occupied 0,65, free 0,25, negate 0 → p = (255 − piksel) / 255.
Piksel 0 → p 1 (engel), 254 → p 0,004 (boş), 128 → p 0,498 (bilinmeyen), 205 → p 0,196: eşiklerle
BOŞ (Nav2 de öyle sayar). map_saver "trinary"de haritalanmamışı 205 yazar: unknown_pixel=205 ile
panel onu haritalanmamış çizer. Gerçek haritada yalnız 0, 205, 254 var.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import map_style as ms  # noqa: E402

MAP = Path(__file__).resolve().parents[2] / "ika_nav" / "maps" / "ika_saha.pgm"


def test_read_pgm_with_comment(tmp_path):
    f = tmp_path / "m.pgm"
    f.write_bytes(b"P5\n# CREATOR: map_saver\n3 2\n255\n" + bytes([0, 128, 254, 205, 255, 1]))
    a = ms.read_pgm(f)
    assert a.shape == (2, 3) and a.tolist() == [[0, 128, 254], [205, 255, 1]]


def test_read_real_map():
    a = ms.read_pgm(MAP)
    assert a.shape == (454, 693)                # ika_saha.yaml'daki harita


def test_classify():
    px = np.array([[0, 254, 128, 205]], dtype=np.uint8)
    out = ms.classify(px, negate=0, occupied_thresh=0.65, free_thresh=0.25)
    assert out.tolist() == [[ms.OCCUPIED, ms.FREE, ms.UNKNOWN, ms.FREE]]     # 205: Nav2'nin kuralı
    out = ms.classify(px, 0, 0.65, 0.25, unknown_pixel=205)
    assert out.tolist() == [[ms.OCCUPIED, ms.FREE, ms.UNKNOWN, ms.UNKNOWN]]   # panel: haritalanmamış
    px = px[:, :3]
    neg = ms.classify(px, negate=1, occupied_thresh=0.65, free_thresh=0.25)
    assert neg.tolist() == [[ms.FREE, ms.OCCUPIED, ms.UNKNOWN]]


def test_real_map_has_all_classes():
    out = ms.classify(ms.read_pgm(MAP), 0, 0.65, 0.25, unknown_pixel=205)
    counts = {c: int((out == c).sum()) for c in (ms.UNKNOWN, ms.FREE, ms.OCCUPIED)}
    assert all(n > 0 for n in counts.values())
    assert counts[ms.FREE] > counts[ms.OCCUPIED]          # saha çoğunlukla boş zemin


def test_scan_points():
    # lidar (1; 2)'de, kuzeye bakıyor (yön 90°); ölçümler −90°, 0°, +90°
    pts = ms.scan_points([1.0, 2.0, 3.0], -math.pi / 2, math.pi / 2, 0.1, 10.0, (1.0, 2.0, math.pi / 2))
    assert pts == pytest.approx(np.array([[2.0, 2.0], [1.0, 4.0], [-2.0, 2.0]]), abs=1e-9)


def test_scan_points_drops_invalid_and_steps():
    r = [float("inf"), 0.05, float("nan"), 5.0, 20.0, 1.0]
    pts = ms.scan_points(r, 0.0, 0.1, 0.1, 10.0, (0.0, 0.0, 0.0))
    assert len(pts) == 2                                   # yalnız 5,0 ve 1,0 menzil içinde
    assert len(ms.scan_points([1.0] * 10, 0.0, 0.1, 0.1, 10.0, (0, 0, 0), step=2)) == 5
