"""Analizin istatistiği (Faz 5, K-068). Standart Python: sistemdeki scipy NumPy sürümüyle uyumsuz.

- wilson: bir oranın %95 güven aralığı (Wilson). Küçük örneklerde (0/15, 15/15) normal
  yaklaşımdan doğru: sınırlar 0'ın altına ya da 1'in üstüne taşmaz.
- mcnemar: iki yapılandırmanın EŞLEŞTİRİLMİŞ karşılaştırması (aynı senaryo + aynı seed, K-053).
  Yalnız sonucu farklı çiftler bilgi taşır: b = yalnız birincide "evet", c = yalnız ikincide.
  Kesin (binom) sürüm: b + c küçükken de doğru. İki yönlü.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Tuple

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> Tuple[float, float, float]:
    """(oran, alt, üst). n = 0 ise (nan, nan, nan)."""
    if n == 0:
        return (math.nan, math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, center - half), min(1.0, center + half))


def mcnemar(b: int, c: int) -> float:
    """Kesin McNemar p değeri (iki yönlü): b + c farklı çiftte b'nin binom(1/2) altında bu kadar
    uç olma olasılığı. Fark yoksa 1."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired(rows: Iterable[Dict], first: str, second: str, outcome) -> Tuple[int, int, int]:
    """Aynı (senaryo, tekrar) çiftleri: (çift sayısı, b, c). outcome(row) → bool.
    b: yalnız `first`te doğru, c: yalnız `second`de doğru."""
    by = {}
    for r in rows:
        by.setdefault((r["senaryo"], r["tekrar"]), {})[r["yapilandirma"]] = outcome(r)
    pairs = [(v[first], v[second]) for v in by.values() if first in v and second in v]
    return (len(pairs), sum(1 for x, y in pairs if x and not y), sum(1 for x, y in pairs if y and not x))
