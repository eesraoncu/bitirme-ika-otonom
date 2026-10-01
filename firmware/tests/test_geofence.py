"""Kartın coğrafi sınır kodu (firmware/app/rules/geofence/) doğru mu.

    python3 -m pytest firmware/tests -v

geofence_driver.c, kartın C kaynağıyla birlikte gcc ile derlenir. Cevaplar
iki yerden denetlenir: elle hesaplanmış durumlar ve Python'daki bağımsız bir
referans. Referans BAŞKA bir algoritma kullanır (dolanma sayısı, sınır için
iç çarpım): iki farklı yöntemin aynı hatayı yapması daha az olası.
"""
from __future__ import annotations

import math
import random
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "firmware" / "app"
TESTS = ROOT / "firmware" / "tests"

ALLOWED_MAX, FORBIDDEN_MAX, FORBIDDEN_VERTICES_MAX = 16, 4, 8
I16_MIN, I16_MAX = -32768, 32767

Point = Tuple[int, int]
Poly = Sequence[Point]

pytestmark = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc yok")


# Sanitizer: dizinin dışını okumak cevabı her zaman değiştirmez (arkadaki
# bellek tesadüfen sıfır olabilir). ASan bunu cevaptan bağımsız yakalar ve
# sürücüyü sıfırdan farklı kodla durdurur.
@pytest.fixture(scope="module")
def driver(tmp_path_factory):
    exe = tmp_path_factory.mktemp("c") / "geofence_driver"
    cc = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wsign-conversion",
         "-Werror", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
         "-I", str(APP), str(TESTS / "geofence_driver.c"),
         str(APP / "rules" / "geofence" / "geofence.c"), "-o", str(exe)],
        capture_output=True, text=True)
    assert cc.returncode == 0, "Kartın C kodu katı uyarılarla derlenmedi:\n" + cc.stderr

    def run(commands: List[str]) -> List[str]:
        r = subprocess.run([str(exe)], input="\n".join(commands) + "\n",
                           capture_output=True, text=True)
        assert r.returncode == 0
        out = r.stdout.splitlines()
        assert len(out) == len(commands)
        return out

    return run


def _poly(cmd: str, poly: Poly) -> str:
    return f"{cmd} {len(poly)} " + " ".join(f"{x} {y}" for x, y in poly)


def check(driver, allowed: Poly, forbidden: Sequence[Poly], points: Sequence[Point]) -> List[str]:
    cmds = [_poly("allowed", allowed)] + [_poly("forbidden", f) for f in forbidden]
    cmds += [f"check {x} {y}" for x, y in points]
    out = driver(cmds)
    assert all(o == "ok" for o in out[:len(cmds) - len(points)])
    return out[len(cmds) - len(points):]


# ---- Python referansı: dolanma sayısı ------------------------------------------

def _cross(a: Point, b: Point, p: Point) -> int:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    """Aynı doğruda ve iki ucun arasında: (p − a)·(p − b) ≤ 0."""
    dot = (p[0] - a[0]) * (p[0] - b[0]) + (p[1] - a[1]) * (p[1] - b[1])
    return _cross(a, b, p) == 0 and dot <= 0


def ref_locate(poly: Poly, p: Point) -> str:
    """'B' sınırda, 'I' içeride, 'O' dışarıda. Python tamsayıları taşmaz."""
    edges = list(zip(poly, poly[1:] + poly[:1]))
    if any(_on_segment(a, b, p) for a, b in edges):
        return "B"
    wn = 0
    for a, b in edges:
        if a[1] <= p[1] < b[1] and _cross(a, b, p) > 0:
            wn += 1
        elif b[1] <= p[1] < a[1] and _cross(a, b, p) < 0:
            wn -= 1
    return "I" if wn != 0 else "O"


def ref_check(allowed: Poly, forbidden: Sequence[Poly], p: Point) -> str:
    if ref_locate(list(allowed), p) != "I":
        return "OUT"
    if any(ref_locate(list(f), p) != "O" for f in forbidden):
        return "FORBID"
    return "OK"


# ---- Elle hesaplanmış durumlar -------------------------------------------------

SQUARE = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]

# Işın atmanın en çok yanıldığı şekil: içbükey "U". Çentik x 1000–2000, y 1000–3000.
U_SHAPE = [(0, 0), (3000, 0), (3000, 3000), (2000, 3000), (2000, 1000),
           (1000, 1000), (1000, 3000), (0, 3000)]

# Köşeleri yatay ve dikey eksende: y = 0'daki ışın iki köşeden geçer.
DIAMOND = [(0, -1000), (1000, 0), (0, 1000), (-1000, 0)]

HAND_CASES = [
    ("kare: orta", SQUARE, [], (500, 500), "OK"),
    ("kare: içte köşeye 1 cm", SQUARE, [], (1, 1), "OK"),
    ("kare: köşe", SQUARE, [], (0, 0), "OUT"),
    ("kare: karşı köşe", SQUARE, [], (1000, 1000), "OUT"),
    ("kare: alt kenar", SQUARE, [], (500, 0), "OUT"),
    ("kare: sağ kenar", SQUARE, [], (1000, 500), "OUT"),
    ("kare: üst kenar", SQUARE, [], (500, 1000), "OUT"),
    ("kare: sol kenar", SQUARE, [], (0, 500), "OUT"),
    ("kare: dışta 1 cm", SQUARE, [], (1001, 500), "OUT"),
    ("kare: alt kenarın uzantısında, dışta", SQUARE, [], (-500, 0), "OUT"),
    ("baklava: orta", DIAMOND, [], (0, 0), "OK"),
    ("baklava: ışın sağ köşeden geçer", DIAMOND, [], (-500, 0), "OK"),
    ("baklava: ışın iki köşeden geçer, dışta", DIAMOND, [], (-1500, 0), "OUT"),
    ("baklava: çapraz kenar", DIAMOND, [], (500, 500), "OUT"),
    ("baklava: çapraz kenarın 1 cm içi", DIAMOND, [], (500, 499), "OK"),
    ("U: sol kol", U_SHAPE, [], (500, 2000), "OK"),
    ("U: çentik", U_SHAPE, [], (1500, 2000), "OUT"),
    ("U: sağ kol", U_SHAPE, [], (2500, 2000), "OK"),
    ("U: taban", U_SHAPE, [], (1500, 500), "OK"),
    ("U: çentiğin tabanı (kenar)", U_SHAPE, [], (1500, 1000), "OUT"),
    ("U: çentiğin kenarı", U_SHAPE, [], (1000, 2000), "OUT"),
    ("U: ışın çentiğin tabanı boyunca gider", U_SHAPE, [], (500, 1000), "OK"),
    ("U: çentiğin ağzı", U_SHAPE, [], (1500, 3000), "OUT"),
    ("U: ışın kolların tepesi boyunca gider, dışta", U_SHAPE, [], (-10, 3000), "OUT"),
]

BIG = [(0, 0), (10000, 0), (10000, 10000), (0, 10000)]
HOLE = [(4000, 4000), (6000, 4000), (6000, 6000), (4000, 6000)]
HOLE_CASES = [
    ("delik: içi", (5000, 5000), "FORBID"),
    ("delik: kenarı", (4000, 5000), "FORBID"),
    ("delik: köşesi", (4000, 4000), "FORBID"),
    ("delik: 1 cm dışı", (3999, 5000), "OK"),
    ("delik: ışın deliğin köşesinden geçer", (1000, 4000), "OK"),
    ("delik: sağında", (7000, 5000), "OK"),
]

# Uç değerler: çapraz çarpım 32 bite sığmaz.
EXTREME = [(I16_MIN, I16_MIN), (I16_MAX, I16_MIN), (I16_MAX, I16_MAX)]
EXTREME_CASES = [
    ("uç üçgen: köşegenin altı", (I16_MAX - 1, I16_MIN + 1), "OK"),
    ("uç üçgen: köşegenin 1 cm altı", (0, -1), "OK"),
    ("uç üçgen: köşegen", (0, 0), "OUT"),
    ("uç üçgen: köşegenin 1 cm üstü", (0, 1), "OUT"),
    ("uç üçgen: karşı köşe yakını, dışta", (I16_MIN + 1, I16_MAX - 1), "OUT"),
    ("uç üçgen: köşe", (I16_MAX, I16_MIN), "OUT"),
]


@pytest.mark.parametrize("name,poly,forb,p,expected", HAND_CASES, ids=[c[0] for c in HAND_CASES])
def test_hand_cases(driver, name, poly, forb, p, expected):
    assert ref_check(poly, forb, p) == expected, "referans elle hesaplananla aynı değil"
    assert check(driver, poly, forb, [p]) == [expected]


@pytest.mark.parametrize("name,p,expected", HOLE_CASES, ids=[c[0] for c in HOLE_CASES])
def test_forbidden_hole(driver, name, p, expected):
    assert ref_check(BIG, [HOLE], p) == expected
    assert check(driver, BIG, [HOLE], [p]) == [expected]


@pytest.mark.parametrize("name,p,expected", EXTREME_CASES, ids=[c[0] for c in EXTREME_CASES])
def test_extreme_coordinates(driver, name, p, expected):
    assert ref_check(EXTREME, [], p) == expected
    assert check(driver, EXTREME, [], [p]) == [expected]


def test_forbidden_outside_allowed_reports_outside(driver):
    """Hem izinli çokgenin dışında hem yasak bölgede: OUTSIDE_ALLOWED önce gelir."""
    forb = [(900, 400), (1100, 400), (1100, 600), (900, 600)]
    assert check(driver, SQUARE, [forb], [(1050, 500), (950, 500)]) == ["OUT", "FORBID"]


# ---- Geçersiz sınır hiçbir şeye izin vermez -------------------------------------

def _circle(n: int, r: int, cx: int = 0, cy: int = 0) -> List[Point]:
    return [(cx + round(r * math.cos(2 * math.pi * i / n)),
             cy + round(r * math.sin(2 * math.pi * i / n))) for i in range(n)]


def test_limits_accepted(driver):
    """Sınırların tam kendisi geçerli: 16 köşe ve 4 × 8 köşe."""
    allowed = _circle(ALLOWED_MAX, 20000)
    holes = [_circle(FORBIDDEN_VERTICES_MAX, 1000, cx, cy)
             for cx, cy in [(-8000, 0), (8000, 0), (0, -8000), (0, 8000)]]
    assert check(driver, allowed, holes, [(0, 0), (8000, 0)]) == ["OK", "FORBID"]


@pytest.mark.parametrize("name,allowed,forbidden", [
    ("izinli 2 köşe", [(0, 0), (1000, 1000)], []),
    ("izinli 17 köşe", _circle(ALLOWED_MAX + 1, 20000), []),
    ("5 yasak çokgen", _circle(8, 20000),
     [_circle(4, 100, 1000 * k + 5000, 0) for k in range(FORBIDDEN_MAX + 1)]),
    ("yasak 9 köşe", _circle(8, 20000), [_circle(FORBIDDEN_VERTICES_MAX + 1, 100, 5000, 0)]),
    ("yasak 2 köşe", _circle(8, 20000), [[(5000, 0), (5100, 0)]]),
], ids=lambda v: v if isinstance(v, str) else "")
def test_invalid_fence_allows_nothing(driver, name, allowed, forbidden):
    # Sınır geçerli olsaydı bu noktaların hepsi OK olurdu. Birden fazla yön:
    # dizinin dışından okunan bir "köşe" çokgeni yalnızca bir yerde bozar.
    points = [(-10000, 0), (0, -10000), (0, 10000), (-7000, 7000), (7000, -7000)]
    assert check(driver, allowed, forbidden, points) == ["OUT"] * len(points)


# ---- Rastgele: C ile referans aynı kararı veriyor mu ------------------------------

def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def sgn(v: int) -> int:
        return (v > 0) - (v < 0)
    d1, d2 = sgn(_cross(c, d, a)), sgn(_cross(c, d, b))
    d3, d4 = sgn(_cross(a, b, c)), sgn(_cross(a, b, d))
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    return ((d1 == 0 and _on_segment(c, d, a)) or (d2 == 0 and _on_segment(c, d, b)) or
            (d3 == 0 and _on_segment(a, b, c)) or (d4 == 0 and _on_segment(a, b, d)))


def _is_simple(poly: Poly) -> bool:
    n = len(poly)
    if len(set(poly)) != n:
        return False
    edges = [(poly[i], poly[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue   # komşu kenarlar ortak köşede buluşur
            if _segments_intersect(*edges[i], *edges[j]):
                return False
    return True


def _star(rng: random.Random, n: int, cx: int, cy: int, rmin: int, rmax: int) -> List[Point]:
    """Merkez etrafında açıya göre sıralı köşeler: içbükey olabilir, kendini kesmez."""
    while True:
        angles = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
        poly = [(max(I16_MIN, min(I16_MAX, cx + round(r * math.cos(t)))),
                 max(I16_MIN, min(I16_MAX, cy + round(r * math.sin(t)))))
                for t, r in ((t, rng.uniform(rmin, rmax)) for t in angles)]
        if _is_simple(poly):
            return poly


def _points_on_edge(a: Point, b: Point) -> List[Point]:
    """Kenarın üstündeki tamsayı noktalar (uçlar hariç, en fazla 3)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    g = math.gcd(dx, dy)
    return [(a[0] + dx // g * k, a[1] + dy // g * k) for k in range(1, min(g, 4))]


def _sample_points(rng: random.Random, polys: Sequence[Poly]) -> List[Point]:
    """Rastgele nokta sınırın üstüne neredeyse hiç düşmez (COBS'taki ders).
    Noktaların bir kısmı bilerek köşe, kenar ve köşe yüksekliğinden seçilir."""
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    pts: List[Point] = []
    for _ in range(30):
        pts.append((rng.randint(lo_x - 50, hi_x + 50), rng.randint(lo_y - 50, hi_y + 50)))
    for poly in polys:
        for i, v in enumerate(poly):
            w = poly[(i + 1) % len(poly)]
            pts.append(v)                                              # köşe
            pts += _points_on_edge(v, w)                               # kenar
            pts.append((rng.randint(lo_x - 50, hi_x + 50), v[1]))     # ışın köşeden geçer
            pts += [(v[0] + dx, v[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return [(max(I16_MIN, min(I16_MAX, x)), max(I16_MIN, min(I16_MAX, y))) for x, y in pts]


@pytest.mark.parametrize("scale", ["küçük", "büyük"])
def test_random_matches_reference(driver, scale):
    rng = random.Random(2026_10_01 if scale == "küçük" else 2026_10_02)
    r_allowed = 5000 if scale == "küçük" else 32000
    cmds: List[str] = []
    expected: List[str] = []
    boundary = 0
    for _ in range(150):
        allowed = _star(rng, rng.randint(3, ALLOWED_MAX), 0, 0, r_allowed // 3, r_allowed)
        holes = [_star(rng, rng.randint(3, FORBIDDEN_VERTICES_MAX),
                       rng.randint(-r_allowed // 2, r_allowed // 2),
                       rng.randint(-r_allowed // 2, r_allowed // 2), r_allowed // 20, r_allowed // 6)
                 for _ in range(rng.randint(0, FORBIDDEN_MAX))]
        cmds.append(_poly("allowed", allowed))
        cmds += [_poly("forbidden", h) for h in holes]
        expected += ["ok"] * (1 + len(holes))
        for p in _sample_points(rng, [allowed] + holes):
            cmds.append(f"check {p[0]} {p[1]}")
            expected.append(ref_check(allowed, holes, p))
            boundary += any(ref_locate(poly, p) == "B" for poly in [allowed] + holes)

    got = driver(cmds)
    diffs = [(c, e, g) for c, e, g in zip(cmds, expected, got) if e != g]
    assert not diffs, f"{len(diffs)} farklı karar, ilki: {diffs[0]}"
    # Her yol sınanmalı, sınır üstü noktalar da azımsanmayacak sayıda
    assert {"OK", "OUT", "FORBID"} <= set(expected)
    assert boundary > 1000, f"yalnızca {boundary} sınır noktası"
