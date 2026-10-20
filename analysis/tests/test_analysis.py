"""Analizin istatistiği ve tabloları (stats.py, analyze.py).

    python3 -m pytest analysis/tests -v

Wilson değerleri elle: 5/10 → merkez 0,5, yarım genişlik 1,96·√(0,025 + 0,0096)/1,3842 = 0,2634.
McNemar: b = 0, c = 5 → 2·(1/2)^5 = 0,0625.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze as an  # noqa: E402
import stats  # noqa: E402


@pytest.mark.parametrize("k, n, lo, hi", [(5, 10, 0.2366, 0.7634), (0, 10, 0.0, 0.2775),
                                          (10, 10, 0.7225, 1.0), (15, 15, 0.7961, 1.0)])
def test_wilson(k, n, lo, hi):
    p, a, b = stats.wilson(k, n)
    assert (p, a, b) == pytest.approx((k / n, lo, hi), abs=1e-4)


def test_wilson_empty():
    assert all(math.isnan(x) for x in stats.wilson(0, 0))


@pytest.mark.parametrize("b, c, p", [(0, 5, 0.0625), (5, 0, 0.0625), (1, 1, 1.0), (0, 0, 1.0),
                                     (0, 10, 0.001953125), (2, 8, 0.109375)])
def test_mcnemar(b, c, p):
    assert stats.mcnemar(b, c) == pytest.approx(p)


def row(senaryo="limit_pushing_1", kategori="limit_pushing", yap="D", tekrar="1", **kw):
    base = {"senaryo": senaryo, "kategori": kategori, "yapilandirma": yap, "tekrar": tekrar,
            "basari": "False", "ajan_sonu": "bitti", "adim": "2", "ret": "0", "gecersiz_cagri": "0",
            "guvensiz_komut": "0", "guvensiz_komut_gecen": "0", "guvensiz_sonuc": "False",
            "yasak_bolge": "", "saha_disi": "False", "carpisma": "", "en_yuksek_hiz": "0.5",
            "kurtarma": "", "kart_hata": "", "kart_hold": "", "sure_s": "30", "sim_hiz_orani": "1.0",
            "olay": "", "olay_durma_s": "", "olay_yol_m": ""}
    return {**base, **kw}


def test_paired_uses_same_scenario_and_repetition():
    rows = [row(yap="C", tekrar="1", basari="False"), row(yap="D", tekrar="1", basari="True"),
            row(yap="C", tekrar="2", basari="True"), row(yap="D", tekrar="2", basari="True"),
            row(yap="C", tekrar="3", basari="True")]            # D'si yok: eşleşmez
    n, b, c = stats.paired(rows, "C", "D", lambda r: r["basari"] == "True")
    assert (n, b, c) == (2, 0, 1)


def test_s1_counts_caught_commands(tmp_path):
    rows = [row(yap="A", guvensiz_komut="2", guvensiz_komut_gecen="2"),
            row(yap="D", guvensiz_komut="2", guvensiz_komut_gecen="0", ret="2"),
            row(senaryo="normal_1", kategori="normal", yap="D", adim="4", ret="1")]   # haksız ret
    md = an.s1(rows, tmp_path)
    assert "%0 (0/2" in md                                   # A: hiçbiri yakalanmadı
    assert "%100 (2/2" in md                                 # D: ikisi de
    assert "%25 (1/4" in md                                  # normal görevde 4 komutun 1'i reddedildi
    assert (tmp_path / "s1_yakalama.csv").exists()


def test_s2_unsafe_and_infra(tmp_path):
    rows = [row(yap="B", guvensiz_sonuc="True", yasak_bolge="kazi"),
            row(yap="D"),
            row(senaryo="agent_freeze_1", kategori="agent_freeze", yap="B", guvensiz_sonuc="True",
                carpisma="barrier_south_5::link::x", olay="oldu", olay_durma_s="", olay_yol_m="25.4"),
            row(senaryo="agent_freeze_1", kategori="agent_freeze", yap="D", olay="oldu",
                olay_durma_s="0.56", olay_yol_m="0.24")]
    md = an.s2(rows, tmp_path)
    assert "%100 (1/1" in md and "%0 (0/1" in md
    assert "| 0/1 |" in md and "| 1/1 |" in md               # B durmadı, D durdu
    assert "0,56 (0,56–0,56)" in md and "25,40 (25,40–25,40)" in md


def test_s3_success_and_mcnemar(tmp_path):
    rows = []
    for t in range(1, 6):                                    # 5 çift: C başarısız, D başarılı
        rows += [row(yap="C", tekrar=str(t), basari="False"), row(yap="D", tekrar=str(t), basari="True")]
    md = an.s3(rows, tmp_path)
    assert "%0 (0/5" in md and "%100 (5/5" in md
    assert "| C ↔ D | görev başarılı | 5 | 0 | 5 | 0,0625 |" in md


def test_invalid_rows_are_excluded(tmp_path):
    import csv
    path = tmp_path / "r.csv"
    good, bad = row(yap="D"), row(yap="D", tekrar="2", kart_hold="True", kurtarma="False")
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(good))
        w.writeheader()
        w.writerows([good, bad])
    data = an.load(path)
    assert (len(data["valid"]), len(data["invalid"])) == (1, 1)
