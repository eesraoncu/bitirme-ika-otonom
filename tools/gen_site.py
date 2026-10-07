#!/usr/bin/env python3
"""shared/site/ika_saha.yaml → kartın site_data.c'si ve Nav2'nin yasak bölge maskesi.

Kullanım:
    python3 tools/gen_site.py            # dosyaları üret
    python3 tools/gen_site.py --check    # üretilmiş dosyalar güncel mi?

K-037: saha tek yerde tanımlanır. Kart ile Nav2 aynı bölgeleri buradan alır.
Üretilen dosyalar elle düzenlenmez.

Adımlar:
1. Güvenlik payı (margin_m, K-036): izinli alan içeri çekilir, yasak bölgeler
   büyür. Santimetreye yuvarlama da güvenli tarafa: izinli alan içeri, yasak
   bölgeler dışarı.
2. Denetim (K-024 bunu veri üretimine bırakmıştı): köşe sınırları, dışbükeylik
   (kenarlar kesişmez), int16 aralığı, home ve güvenli noktaların izinli alanda
   ve yasak bölgelerin dışında olması. Hata varsa hiçbir dosya yazılmaz.
3. site_data.c (kart, int16 cm).
4. Maske: haritayla aynı ızgara. Her hücrenin merkezi kartın kuralıyla
   (geofence_cm, aşağıda) denetlenir; kartın reddedeceği hücre kapalıdır.
   İzinli alanın dışı da kapalı: Nav2 kapıdan dışarı da plan yapmaz.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "shared" / "site" / "ika_saha.yaml"
MAP_YAML = ROOT / "ros2_ws" / "src" / "ika_nav" / "maps" / "ika_saha.yaml"
OUT_C = ROOT / "firmware" / "app" / "site" / "site_data.c"
OUT_MASK_PGM = ROOT / "ros2_ws" / "src" / "ika_nav" / "maps" / "ika_saha_keepout.pgm"
OUT_MASK_YAML = ROOT / "ros2_ws" / "src" / "ika_nav" / "maps" / "ika_saha_keepout.yaml"

# firmware/app/rules/geofence/geofence.h ve site/site.h ile aynı olmalı
ALLOWED_MAX, FORBIDDEN_MAX, FORBIDDEN_VERTICES_MAX = 16, 4, 8
SAFE_POINTS_MAX = 8
I16_MIN, I16_MAX = -32768, 32767

# geofence_result_t
OK, OUTSIDE_ALLOWED, IN_FORBIDDEN = 0, 1, 2

# Maske pikselleri (map_server, trinary): siyah = dolu (keepout), beyaz = boş
MASK_BLOCKED, MASK_FREE = 0, 254

NAME = re.compile(r"^[a-z][a-z0-9_]*$")

Pt = Tuple[float, float]
PtCm = Tuple[int, int]


class SiteError(ValueError):
    pass


# ---- geometri ---------------------------------------------------------------

def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _signed_area(poly: Sequence[Pt]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, list(poly[1:]) + [poly[0]])) / 2


def ccw(poly: Sequence[Pt]) -> List[Pt]:
    """Saat yönünün tersine sırala (pay hesabı yönü bilmeli)."""
    return list(poly) if _signed_area(poly) > 0 else list(reversed(poly))


def check_convex(name: str, poly: Sequence[Pt]) -> None:
    """Kesin dışbükey: her köşede aynı yöne dönülür, üç köşe aynı doğruda değil.
    Dışbükey çokgenin kenarları birbirini kesmez (basit çokgen)."""
    n = len(poly)
    for i in range(n):
        if _cross(poly[i], poly[(i + 1) % n], poly[(i + 2) % n]) <= 0:
            raise SiteError(f"{name}: dışbükey değil ya da üç köşe aynı doğruda (köşe {i + 1})")


def offset(poly: Sequence[Pt], d: float) -> List[Pt]:
    """Dışbükey, saat yönü tersi çokgeni d kadar dışarı (d < 0: içeri) kaydır:
    her kenar normali yönünde ötelenir, komşu kenarların kesişimi yeni köşedir."""
    n = len(poly)
    lines = []
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        ln = math.hypot(x2 - x1, y2 - y1)
        nx, ny = (y2 - y1) / ln, -(x2 - x1) / ln          # saat yönü tersinde dış normal
        lines.append(((x1 + nx * d, y1 + ny * d), (x2 - x1, y2 - y1)))
    out = []
    for i in range(n):
        (p, r), (q, s) = lines[i - 1], lines[i]
        denom = r[0] * s[1] - r[1] * s[0]
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / denom
        out.append((p[0] + t * r[0], p[1] + t * r[1]))
    return out


def to_cm(poly: Sequence[Pt], outward: bool) -> List[PtCm]:
    """Metre → cm, güvenli tarafa yuvarla: merkeze göre dışarı (yasak bölge)
    ya da içeri (izinli alan). Eksenlere paralel kenarlarda tam doğrudur."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)

    def r(v: float, c: float) -> int:
        v = round(v * 100, 6)                      # 2.595*100 = 259.49999... gibi kayan nokta artıkları
        away = (v > c * 100) == outward
        return math.ceil(v) if away else math.floor(v)

    return [(r(x, cx), r(y, cy)) for x, y in poly]


def point_cm(p: Pt) -> PtCm:
    """Tek nokta (home, güvenli nokta, hücre merkezi) → en yakın cm."""
    return (math.floor(p[0] * 100 + 0.5), math.floor(p[1] * 100 + 0.5))


# ---- kartın kuralı (K-024): sınırın üstü ihlal ------------------------------

def _where(poly: Sequence[PtCm], p: PtCm) -> str:
    """'on' (kenarın üstü), 'in' ya da 'out'. Tamsayı; dolanma sayısıyla."""
    n, wn = len(poly), 0
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        c = _cross(a, b, p)
        if c == 0 and (p[0] - a[0]) * (p[0] - b[0]) + (p[1] - a[1]) * (p[1] - b[1]) <= 0:
            return "on"
        if a[1] <= p[1] < b[1] and c > 0:
            wn += 1
        elif b[1] <= p[1] < a[1] and c < 0:
            wn -= 1
    return "in" if wn != 0 else "out"


def geofence_cm(allowed: Sequence[PtCm], forbidden: Sequence[Sequence[PtCm]], p: PtCm) -> int:
    """geofence_check()'in Python'daki eşi. Testler ikisini her hücrede karşılaştırır."""
    if _where(allowed, p) != "in":
        return OUTSIDE_ALLOWED
    if any(_where(f, p) != "out" for f in forbidden):
        return IN_FORBIDDEN
    return OK


# ---- yükle, uygula, denetle -------------------------------------------------

def _poly(name: str, raw) -> List[Pt]:
    try:
        poly = [(float(x), float(y)) for x, y in raw]
    except (TypeError, ValueError):
        raise SiteError(f"{name}: köşeler [x, y] listesi olmalı")
    if len(poly) < 3:
        raise SiteError(f"{name}: en az 3 köşe gerekir")
    return poly


def _point(name: str, raw) -> Pt:
    try:
        x, y = raw
        return (float(x), float(y))
    except (TypeError, ValueError):
        raise SiteError(f"{name}: [x, y] olmalı")


def build(src: Dict) -> Dict:
    """Kaynağı doğrula ve pay uygulanmış, cm cinsinden sahayı döndür."""
    margin = float(src.get("margin_m", -1))
    if not 0 <= margin <= 5:
        raise SiteError("margin_m 0 ile 5 m arasında olmalı")

    allowed = ccw(_poly("allowed", src.get("allowed")))
    if len(allowed) > ALLOWED_MAX:
        raise SiteError(f"allowed: en çok {ALLOWED_MAX} köşe")
    check_convex("allowed", allowed)

    forb_src = src.get("forbidden") or {}
    if len(forb_src) > FORBIDDEN_MAX:
        raise SiteError(f"forbidden: en çok {FORBIDDEN_MAX} bölge")
    forbidden = {}
    for name, raw in forb_src.items():
        if not NAME.match(str(name)):
            raise SiteError(f"forbidden: '{name}' küçük harf, rakam ve _ olmalı")
        poly = ccw(_poly(f"forbidden.{name}", raw))
        if len(poly) > FORBIDDEN_VERTICES_MAX:
            raise SiteError(f"forbidden.{name}: en çok {FORBIDDEN_VERTICES_MAX} köşe")
        check_convex(f"forbidden.{name}", poly)
        forbidden[name] = poly

    allowed_cm = to_cm(offset(allowed, -margin), outward=False)
    check_convex("allowed (paydan sonra)", allowed_cm)
    forbidden_cm = {n: to_cm(offset(p, margin), outward=True) for n, p in forbidden.items()}

    for name, poly in [("allowed", allowed_cm)] + [(f"forbidden.{n}", p) for n, p in forbidden_cm.items()]:
        for x, y in poly:
            if not (I16_MIN <= x <= I16_MAX and I16_MIN <= y <= I16_MAX):
                raise SiteError(f"{name}: ({x}, {y}) cm int16 aralığının dışında")

    home = point_cm(_point("home", src.get("home")))
    safe_src = src.get("safe_points") or {}
    if not 1 <= len(safe_src) <= SAFE_POINTS_MAX:
        raise SiteError(f"safe_points: 1 ile {SAFE_POINTS_MAX} arası nokta")
    safe = {}
    for name, raw in safe_src.items():
        if not NAME.match(str(name)):
            raise SiteError(f"safe_points: '{name}' küçük harf, rakam ve _ olmalı")
        safe[name] = point_cm(_point(f"safe_points.{name}", raw))

    forb_list = list(forbidden_cm.values())
    for name, p in [("home", home)] + [(f"safe_points.{n}", p) for n, p in safe.items()]:
        verdict = geofence_cm(allowed_cm, forb_list, p)
        if verdict != OK:
            why = "izinli alanın dışında" if verdict == OUTSIDE_ALLOWED else "yasak bölgede"
            raise SiteError(f"{name} ({p[0]}, {p[1]}) cm, paydan sonra {why}")

    return {"margin_m": margin, "allowed": allowed_cm, "forbidden": forbidden_cm,
            "home": home, "safe": safe}


# ---- çıktılar ---------------------------------------------------------------

GENERATED_NOTE = (
    "OTOMATİK ÜRETİLDİ. ELLE DÜZENLEMEYİN.\n"
    "Kaynak: shared/site/ika_saha.yaml\n"
    "Üretici: tools/gen_site.py"
)


def _c_points(pts: Sequence[PtCm]) -> str:
    return ", ".join(f"{{{x}, {y}}}" for x, y in pts)


def render_c(site: Dict) -> str:
    forb = site["forbidden"]
    lines = ["/* " + GENERATED_NOTE.replace("\n", "\n * "),
             " *",
             f" * Koordinatlar cm, harita çerçevesi. Güvenlik payı {site['margin_m']:g} m uygulandı",
             " * (K-036): izinli alan içeri çekildi, yasak bölgeler büyütüldü. */",
             '#include "site/site.h"',
             "",
             "const site_t site = {",
             "    .fence = {",
             "        .allowed = {",
             f"            .n = {len(site['allowed'])},",
             f"            .v = {{ {_c_points(site['allowed'])} }},",
             "        },",
             f"        .n_forbidden = {len(forb)},",
             "        .forbidden = {"]
    for name, poly in forb.items():
        lines.append(f"            {{ .n = {len(poly)}, .v = {{ {_c_points(poly)} }} }},   /* {name} */")
    lines += ["        },",
              "    },",
              f"    .home = {{{site['home'][0]}, {site['home'][1]}}},",
              f"    .n_safe = {len(site['safe'])},",
              "    .safe = {"]
    for name, (x, y) in site["safe"].items():
        lines.append(f"        {{{x}, {y}}},   /* {name} */")
    lines += ["    },", "};", ""]
    return "\n".join(lines)


def load_map_grid() -> Dict:
    meta = yaml.safe_load(MAP_YAML.read_text(encoding="utf-8"))
    w, h = Image.open(MAP_YAML.parent / meta["image"]).size
    return {"resolution": float(meta["resolution"]), "origin": [float(v) for v in meta["origin"][:2]],
            "width": w, "height": h}


def cell_centers_cm(grid: Dict):
    """Hücre merkezleri (cm). Satır 0 resmin üstü, yani y'nin en büyüğü."""
    res, (ox, oy), w, h = grid["resolution"], grid["origin"], grid["width"], grid["height"]
    for row in range(h):
        y = oy + (h - 1 - row + 0.5) * res
        for col in range(w):
            yield row, col, point_cm((ox + (col + 0.5) * res, y))


def render_mask(site: Dict, grid: Dict) -> np.ndarray:
    forb = list(site["forbidden"].values())
    mask = np.full((grid["height"], grid["width"]), MASK_FREE, dtype=np.uint8)
    for row, col, p in cell_centers_cm(grid):
        if geofence_cm(site["allowed"], forb, p) != OK:
            mask[row, col] = MASK_BLOCKED
    return mask


def render_mask_yaml(grid: Dict) -> str:
    ox, oy = grid["origin"]
    return (f"# {GENERATED_NOTE.replace(chr(10), chr(10) + '# ')}\n"
            "# Nav2 keepout maskesi: siyah = kartın reddedeceği yer (yasak bölge ya da izinli\n"
            "# alanın dışı). Izgara ika_saha.yaml ile aynı.\n"
            f"image: {OUT_MASK_PGM.name}\n"
            "mode: trinary\n"
            f"resolution: {grid['resolution']:g}\n"
            f"origin: [{ox:g}, {oy:g}, 0]\n"
            "negate: 0\n"
            "occupied_thresh: 0.65\n"
            "free_thresh: 0.25\n")


def pgm_bytes(mask: np.ndarray) -> bytes:
    h, w = mask.shape
    return f"P5\n{w} {h}\n255\n".encode() + mask.tobytes()


def outputs() -> Dict[Path, bytes]:
    site = build(yaml.safe_load(SOURCE.read_text(encoding="utf-8")))
    grid = load_map_grid()
    return {
        OUT_C: render_c(site).encode(),
        OUT_MASK_PGM: pgm_bytes(render_mask(site, grid)),
        OUT_MASK_YAML: render_mask_yaml(grid).encode(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="dosyalar güncel mi, yazmadan denetle")
    args = ap.parse_args()
    try:
        files = outputs()
    except SiteError as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1
    stale = [p for p, data in files.items() if not p.exists() or p.read_bytes() != data]
    if args.check:
        for p in stale:
            print(f"güncel değil: {p.relative_to(ROOT)}")
        return 1 if stale else 0
    for p, data in files.items():
        p.write_bytes(data)
        print(f"{p.relative_to(ROOT)}: {len(data)} bayt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
