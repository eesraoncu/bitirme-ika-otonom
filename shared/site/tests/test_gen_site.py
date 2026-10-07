"""Saha üreteci (tools/gen_site.py) ve ürettikleri doğru mu.

    python3 -m pytest shared/site/tests -v

En önemli test: Nav2'nin maskesi ile kartın kararı her hücrede aynı mı. Kartın
gerçek C kodu (geofence.c) üretilmiş site_data.c ile gcc'de derlenir ve maskenin
her hücre merkezi ona sorulur.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import gen_site as gs  # noqa: E402

APP = ROOT / "firmware" / "app"


@pytest.fixture(scope="module")
def source():
    return yaml.safe_load(gs.SOURCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def site(source):
    return gs.build(source)


# ---- üretilmiş dosyalar güncel ----------------------------------------------

def test_outputs_up_to_date():
    for path, data in gs.outputs().items():
        assert path.read_bytes() == data, f"{path.name} güncel değil: python3 tools/gen_site.py"


# ---- pay ve yuvarlama ---------------------------------------------------------

def test_margin_applied(site):
    # izinli alan: bariyer iç yüzü (±0,405 m) − 1 m, içeri yuvarlanmış
    assert sorted(site["allowed"]) == sorted([(-159, -859), (2759, -859), (2759, 859), (-159, 859)])
    assert sorted(site["forbidden"]["kazi"]) == sorted([(1200, -250), (1700, -250), (1700, 250), (1200, 250)])
    assert sorted(site["forbidden"]["personel"]) == sorted([(200, -920), (1000, -920), (1000, -350), (200, -350)])


def test_rounding_safe_side():
    # 1,234 m kenar: izinli alanda içeri (alt kenar yukarı, üst kenar aşağı),
    # yasak bölgede dışarı yuvarlanır
    sq = [(0.0, 0.0), (1.234, 0.0), (1.234, 1.234), (0.0, 1.234)]
    assert gs.to_cm(sq, outward=False)[2] == (123, 123)
    assert gs.to_cm(sq, outward=True)[2] == (124, 124)
    assert gs.to_cm([(-1.235, -1.235), (1, -1.235), (1, 1), (-1.235, 1)], outward=True)[0] == (-124, -124)


def test_offset_square():
    sq = gs.ccw([(0, 0), (0, 2), (2, 2), (2, 0)])        # saat yönünde verilmiş
    out = gs.offset(sq, 0.5)
    assert sorted((round(x, 9), round(y, 9)) for x, y in out) == [(-0.5, -0.5), (-0.5, 2.5), (2.5, -0.5), (2.5, 2.5)]


# ---- kartın kuralı: sınırın üstü ihlal (K-024) ------------------------------

def test_geofence_boundary_is_violation(site):
    a, f = site["allowed"], list(site["forbidden"].values())
    assert gs.geofence_cm(a, f, (0, 0)) == gs.OK
    assert gs.geofence_cm(a, f, (-159, 0)) == gs.OUTSIDE_ALLOWED      # izinli kenarın üstü
    assert gs.geofence_cm(a, f, (-158, 0)) == gs.OK
    assert gs.geofence_cm(a, f, (1200, 0)) == gs.IN_FORBIDDEN          # kazı kenarının üstü
    assert gs.geofence_cm(a, f, (1199, 0)) == gs.OK
    assert gs.geofence_cm(a, f, (1450, 0)) == gs.IN_FORBIDDEN
    assert gs.geofence_cm(a, f, (2800, 0)) == gs.OUTSIDE_ALLOWED      # kapıdan dışarı


# ---- yanlış veri: üreteç durur ----------------------------------------------

@pytest.mark.parametrize("mutate, message", [
    (lambda s: s["forbidden"].update(a=[[0, 0], [1, 0], [1, 1]], b=[[2, 2], [3, 2], [3, 3]]), "en çok 4 bölge"),
    (lambda s: s["forbidden"].update(kazi=[[13, -1.5], [16, 1.5], [16, -1.5], [13, 1.5]]), "dışbükey"),
    (lambda s: s["forbidden"].update(kazi=[[13, 0], [14, 0], [15, 0], [14, 1]]), "dışbükey"),
    (lambda s: s["forbidden"].update(kazi=[[13 + i, (i % 2) * 0.1] for i in range(9)]), "en çok 8 köşe"),
    (lambda s: s["safe_points"].update(kazi_ici=[14.5, 0]), "yasak bölgede"),
    (lambda s: s["safe_points"].update(duvar_dibi=[28, 0]), "izinli alanın dışında"),
    (lambda s: s.update(home=[5, -4]), "yasak bölgede"),     # personel
    (lambda s: s.update(allowed=[[-400, -10], [400, -10], [400, 10], [-400, 10]]), "int16"),
    (lambda s: s.update(allowed=[[-3, -1], [29, -1], [29, 1], [-3, 1]]), "paydan sonra"),   # 2 m: pay yok eder
    (lambda s: s.update(margin_m=-1), "margin_m"),
    (lambda s: s["forbidden"].update({"Kazi2": [[0, 0], [1, 0], [1, 1]]}), "küçük harf"),
])
def test_bad_source_rejected(source, mutate, message):
    bad = copy.deepcopy(source)
    mutate(bad)
    with pytest.raises(gs.SiteError, match=message):
        gs.build(bad)


def test_guvenli_nokta_paydan_sonra_denetlenir(source):
    # kazının 0,5 m güneyi: gerçek bölgenin dışında ama 1 m payın içinde
    bad = copy.deepcopy(source)
    bad["safe_points"]["kazi_yani"] = [14.5, -2.0]
    with pytest.raises(gs.SiteError, match="paydan sonra yasak bölgede"):
        gs.build(bad)


# ---- maske = kartın kararı (asıl tutarlılık testi) --------------------------

@pytest.fixture(scope="module")
def card(tmp_path_factory):
    if shutil.which("gcc") is None:
        pytest.skip("gcc yok")
    exe = tmp_path_factory.mktemp("c") / "site_driver"
    cc = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wsign-conversion",
         "-Werror", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
         "-I", str(APP), str(Path(__file__).parent / "site_driver.c"),
         str(APP / "site" / "site_data.c"), str(APP / "rules" / "geofence" / "geofence.c"),
         "-o", str(exe)],
        capture_output=True, text=True)
    assert cc.returncode == 0, "Kartın C kodu katı uyarılarla derlenmedi:\n" + cc.stderr

    def ask(points):
        r = subprocess.run([str(exe)], input="".join(f"{x} {y}\n" for x, y in points),
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return np.array([int(v) for v in r.stdout.split()])

    return ask


def test_mask_matches_card_every_cell(card):
    grid = gs.load_map_grid()
    cells = list(gs.cell_centers_cm(grid))
    verdict = card([p for _, _, p in cells])
    assert len(verdict) == len(cells) == grid["width"] * grid["height"]

    mask = np.array(Image.open(gs.OUT_MASK_PGM))
    blocked = np.array([mask[r, c] == gs.MASK_BLOCKED for r, c, _ in cells])
    rejects = verdict != gs.OK
    diff = int(np.count_nonzero(blocked != rejects))
    assert diff == 0, f"{diff} hücrede maske ile kart farklı"
    # anlamlı bir harita: hem açık hem kapalı hücre çok
    assert 0.3 < rejects.mean() < 0.8


def test_card_safe_points_ok(card, site):
    pts = [site["home"]] + list(site["safe"].values())
    assert list(card(pts)) == [gs.OK] * len(pts)
