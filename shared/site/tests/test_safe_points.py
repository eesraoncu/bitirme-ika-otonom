"""Kurtarma hedeflerine Nav2 ulaşabiliyor mu (RULES §5.3).

    python3 -m pytest shared/site/tests -v

Kart kurtarmada aracı en yakın güvenli noktaya (ya da başlangıca) gönderir. Nav2
oraya varamazsa kart RECOVERY'de kalır. Ölçüt: araç noktada her yönde durup
dönebilmeli, yani Nav2'nin izi + payının dönüş yarıçapı içinde ne harita engeli ne
keepout hücresi olmalı. Böylece kartın gönderdiği varış yönü önemsiz olur.

İz ve pay Nav2'nin ayarından, harita ve maske ika_nav/maps'ten okunur; burada
kopyası yok. Bilinmeyen (gri) hücre boş sayılır: yerel costmap'te
track_unknown_space kapalı, RPP'nin çarpışma denetimi onu kullanır.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import gen_site as gs  # noqa: E402

NAV2_PARAMS = ROOT / "ros2_ws" / "src" / "ika_nav" / "config" / "nav2_params.yaml"


def rotation_radius() -> float:
    """İzin (+ pay) en uzak köşesinin base_link'e uzaklığı: yerinde dönerken süpürülen daire."""
    p = yaml.safe_load(NAV2_PARAMS.read_text(encoding="utf-8"))
    local = p["local_costmap"]["local_costmap"]["ros__parameters"]
    pad = local["footprint_padding"]
    return max(math.hypot(abs(x) + pad, abs(y) + pad) for x, y in yaml.safe_load(local["footprint"]))


def occupied_centers(map_yaml: Path) -> np.ndarray:
    """Haritadaki dolu hücrelerin merkezleri (m), map_server'ın trinary yorumuyla."""
    meta = yaml.safe_load(map_yaml.read_text(encoding="utf-8"))
    img = np.asarray(Image.open(map_yaml.parent / meta["image"]), dtype=float)
    occ = (255.0 - img) / 255.0 > meta["occupied_thresh"]          # negate: 0
    rows, cols = np.nonzero(occ)
    ox, oy, res = meta["origin"][0], meta["origin"][1], meta["resolution"]
    h = img.shape[0]
    return np.stack([ox + (cols + 0.5) * res, oy + (h - 1 - rows + 0.5) * res], axis=1)


@pytest.fixture(scope="module")
def obstacles() -> np.ndarray:
    return np.concatenate([occupied_centers(gs.MAP_YAML), occupied_centers(gs.OUT_MASK_YAML)])


def clearance(obstacles: np.ndarray, x: float, y: float) -> float:
    """Noktadan en yakın dolu hücrenin kenarına uzaklık (merkez − yarım köşegen, güvenli yön)."""
    half_diag = 0.05 * math.sqrt(2) / 2
    return float(np.min(np.hypot(obstacles[:, 0] - x, obstacles[:, 1] - y))) - half_diag


def test_rotation_radius_from_nav2():
    # iz 1,78 × 1,15 m, base_link'ten arkası 0,99; pay 0,3 (K-038)
    assert rotation_radius() == pytest.approx(math.hypot(0.99 + 0.3, 0.575 + 0.3))


def test_safe_points_and_home_rotation_clear(obstacles):
    site = gs.load_site()
    r = rotation_radius()
    points = {"home": site["home"], **site["safe"]}
    short = {name: round(clearance(obstacles, x / 100, y / 100), 3)
             for name, (x, y) in points.items() if clearance(obstacles, x / 100, y / 100) < r}
    assert not short, f"dönüş yarıçapı {r:.3f} m, yetmeyen noktalar (boşluk, m): {short}"


@pytest.mark.parametrize("name, x, y", [
    ("eski konteyner_onu: konteynere değiyordu", 8.0, 2.0),
    ("eski konteyner_arkasi: kuzey sınırına 12 cm", 8.0, 7.6),
])
def test_detects_blocked_point(obstacles, name, x, y):
    # denetimin kendisi çalışıyor mu: 2026-10-14'te Nav2'nin ulaşamadığı noktalar yakalanmalı
    assert clearance(obstacles, x, y) < rotation_radius(), name


# ---- Ajanın yer adları (places, K-044, Faz 4.3) ---------------------------------
# Güvenli noktalardan farklı: her yönde değil, kendi varış yönünde iz temiz olmalı.

def footprint_margin(obstacles: np.ndarray, x: float, y: float, yaw: float) -> float:
    """Paylı iz dikdörtgeninin (yaw yönünde) en yakın dolu hücreye uzaklığı, içerideyse < 0."""
    p = yaml.safe_load(NAV2_PARAMS.read_text(encoding="utf-8"))
    local = p["local_costmap"]["local_costmap"]["ros__parameters"]
    pad = local["footprint_padding"]
    fp = yaml.safe_load(local["footprint"])
    front = max(a for a, _ in fp) + pad
    back = min(a for a, _ in fp) - pad
    half = max(abs(b) for _, b in fp) + pad
    c, s = math.cos(yaw), math.sin(yaw)
    dx, dy = obstacles[:, 0] - x, obstacles[:, 1] - y
    lx, ly = dx * c + dy * s, -dx * s + dy * c
    out_x = np.maximum(np.maximum(back - lx, lx - front), 0)
    out_y = np.maximum(np.abs(ly) - half, 0)
    d = np.hypot(out_x, out_y) - 0.05 * math.sqrt(2) / 2      # hücrenin kenarı, güvenli yön
    inside = (lx >= back) & (lx <= front) & (np.abs(ly) <= half)
    return float(np.where(inside, -1.0, d).min())


def test_places_footprint_clear_at_heading(obstacles):
    places = gs.load_site()["places"]
    assert places, "places boş"
    short = {name: round(footprint_margin(obstacles, x / 100, y / 100, yaw / 1000), 3)
             for name, (x, y, yaw) in places.items()
             if footprint_margin(obstacles, x / 100, y / 100, yaw / 1000) <= 0}
    assert not short, f"izi engele/keepout'a değen yerler (boşluk, m): {short}"


def test_places_check_catches_bad_heading(obstacles):
    # 2026-10-14 tur 1: (8; 7,6) 43,5° yönle kuzey sınırına taşıyordu
    assert footprint_margin(obstacles, 8.0, 7.6, math.radians(43.5)) <= 0


def test_places_names_do_not_clash_with_safe_points():
    site = gs.load_site()
    assert not set(site["places"]) & set(site["safe"])
