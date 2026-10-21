"""Harita ve lidar verisinin çizime hazırlanması (numpy; ROS'a ve Qt'ye bağlı değil).

Nav2'nin haritası PGM (P5) görüntüsüdür; her piksel doluluk olasılığını taşır. Panel ham
gri görüntüyü değil sınıflarını çizer: boş zemin, engel, haritalanmamış. Eşikler haritanın
kendi yaml'ından (occupied_thresh, free_thresh, negate), map_server'ın kuralıyla:
negate 0 iken p = (255 − piksel) / 255; p > occupied → engel, p < free → boş.
Bir fark: "trinary" haritada map_saver haritalanmamış hücreyi tam 205 yazar; p = 0,196 <
free_thresh 0,25 olduğu için Nav2 onu BOŞ sayar. Panel haritanın kaydettiğini gösterir:
unknown_pixel verilirse o değer haritalanmamış çizilir (Nav2'nin davranışı değişmez).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np

UNKNOWN, FREE, OCCUPIED = 0, 1, 2


def read_pgm(path: Path) -> np.ndarray:
    """P5 (ikili, 8 bit) PGM → (satır, sütun) uint8 dizi. Başlıkta # yorum satırı olabilir."""
    data = Path(path).read_bytes()
    fields, pos = [], 0
    while len(fields) < 4:                       # P5, genişlik, yükseklik, en büyük değer
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            pos = data.index(b"\n", pos) + 1
            continue
        end = pos
        while not data[end:end + 1].isspace():
            end += 1
        fields.append(data[pos:end])
        pos = end
    if fields[0] != b"P5" or int(fields[3]) > 255:
        raise ValueError(f"{path}: yalnız 8 bitlik P5 PGM okunur")
    w, h = int(fields[1]), int(fields[2])
    pos += 1                                     # başlıktan sonraki tek boşluk
    return np.frombuffer(data, dtype=np.uint8, count=w * h, offset=pos).reshape(h, w)


def classify(pixels: np.ndarray, negate: int, occupied_thresh: float, free_thresh: float,
             unknown_pixel: Optional[int] = None) -> np.ndarray:
    p = pixels.astype(np.float32) / 255.0
    occ = p if negate else 1.0 - p
    out = np.full(pixels.shape, UNKNOWN, dtype=np.uint8)
    out[occ > occupied_thresh] = OCCUPIED
    out[occ < free_thresh] = FREE
    if unknown_pixel is not None:
        out[pixels == unknown_pixel] = UNKNOWN
    return out


def scan_points(ranges: Sequence[float], angle_min: float, angle_increment: float,
                range_min: float, range_max: float, pose: Tuple[float, float, float],
                step: int = 1) -> np.ndarray:
    """Lidar ölçümleri → harita çerçevesinde (N, 2) noktalar. pose: lidarın haritadaki
    (x, y, yön). Menzil dışı, sonsuz ve NaN ölçümler atılır (engel yok demektir)."""
    r = np.asarray(ranges, dtype=np.float64)[::step]
    a = angle_min + angle_increment * step * np.arange(r.size)
    ok = np.isfinite(r) & (r >= range_min) & (r <= range_max)
    r, a = r[ok], a[ok] + pose[2]
    return np.column_stack((pose[0] + r * np.cos(a), pose[1] + r * np.sin(a)))
