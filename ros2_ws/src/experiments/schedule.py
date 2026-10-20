"""Koşuların sırası ve tam deneyin bölünerek koşulması (Faz 5, K-067). ROS'a bağlı değil.

- run_order: TEKRAR öncelikli: önce 1. tekrarın bütün senaryo × yapılandırmaları, sonra 2. Nerede
  durulursa durulsun biten her tekrar dört yapılandırmayı eşleşmiş içerir (K-053).
- Altyapı senaryolarında tekrar en çok INFRA_REPS (K-015); LLM senaryolarında --seeds ne derse.
- done_keys: results.csv'de olan koşular (--skip-done: kaldığı yerden devam).
- invalid: geçersiz koşular (--invalid listeler, --drop-invalid CSV'den çıkarır; kayıtları kalır).
- deadline: --until SS:DD → o saatten sonra yeni koşu başlamaz.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

INFRA = ("agent_freeze", "link_loss")
INFRA_REPS = 10            # K-015: altyapı arızasında 10 tekrar
SIM_RATIO_MIN = 0.9        # pilotta hep ~1,0; altı: bilgisayar yüklüydü (K-055)

Key = Tuple[str, str, str]  # (senaryo, yapılandırma, tekrar)


def seeds(text: str) -> List[int]:
    """"1", "1-3", "1,4", "1-3,7" → [..]."""
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def run_order(specs: Iterable[Dict], configs: Iterable[str], seed_list: Iterable[int]) -> List[Tuple[Dict, str, int]]:
    specs, configs = list(specs), list(configs)
    order = []
    for seed in seed_list:
        for spec in specs:
            if spec["category"] in INFRA and seed > INFRA_REPS:
                continue
            for config in configs:
                if config in spec.get("configs", list("ABCD")):
                    order.append((spec, config, seed))
    return order


def read_rows(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key(row: Dict) -> Key:
    return (row["senaryo"], row["yapilandirma"], str(row["tekrar"]))


def done_keys(rows: Iterable[Dict]) -> Set[Key]:
    return {key(r) for r in rows}


def invalid(row: Dict) -> str:
    """Koşu geçersizse nedeni, değilse "". Kayıt düzeninin bozduğu koşular, ajanın ya da kartın
    davranışı değil."""
    if row.get("kart_hold") == "True" and row.get("kurtarma") != "True":
        return "kurtarma olmadan HOLD (kalp atışı kaybı)"
    ratio = row.get("sim_hiz_orani")
    if ratio not in (None, "") and float(ratio) < SIM_RATIO_MIN:
        return f"simülasyon yavaş ({ratio})"
    if row.get("olay") == "olmadı":
        return "altyapı olayı gerçekleşmedi"
    return ""


def write_rows(path: Path, rows: List[Dict], fields: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def deadline(text: str, now: dt.datetime) -> dt.datetime:
    """"SS:DD" → şimdiden sonraki ilk o saat (08:00 gece başlatılırsa ertesi sabah)."""
    h, m = (int(v) for v in text.split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)
