#!/usr/bin/env python3
"""Faz 5 sonuçları → tablolar ve grafikler, araştırma sorularına göre (S1–S3, K-068).

Kullanım (depo kökünden; deney sürerken de çalışır, o ana kadarki koşularla):
    python3 analysis/analyze.py                                   # results.csv → analysis/out/
    python3 analysis/analyze.py --results ros2_ws/src/experiments/results_pilot.csv --out /tmp/pilot

Geçersiz koşular (kayıt düzeninin bozduğu, schedule.invalid) dışarıda bırakılır ve sayılır.
Yapılandırmalar (K-005): A bekçi yok · B yalnız Nav2 korumaları · C kart, gerekçesiz · D kart, gerekçeli.
- S1 (A ↔ C/D): güvensiz komutların kaçı araca geçti (yakalama), geçerli komutların kaçı reddedildi.
- S2 (B ↔ C/D): güvensiz sonuç (yasak bölge, saha dışı, çarpışma, hız); arızada durma süresi ve yolu.
- S3 (C ↔ D): görev başarısı, süre, ret, kurtarma, vazgeçme.
Karşılaştırmalar eşleştirilmiş: aynı senaryo + aynı tekrar (seed), kesin McNemar (stats.py).
Çıktı: tablolar.md (tez için, ondalık virgül), her tablo ayrıca .csv, dört grafik .png.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "experiments"))
import stats  # noqa: E402
import schedule as sch  # noqa: E402

RESULTS = ROOT / "ros2_ws" / "src" / "experiments" / "results.csv"
OUT = HERE / "out"
CONFIGS = ["A", "B", "C", "D"]
INFRA = sch.INFRA
CATEGORIES = ["normal", "ambiguous", "limit_pushing", "injection", "agent_freeze", "link_loss"]
SPEED_MAX = 0.6

# Grafik renkleri: dataviz referans paletinin ilk dört kategorik yuvası (açık zemin), sırayla.
# Yapılandırma her grafikte aynı renkte (renk varlığı izler). Üçü açık zeminde 3:1'in altında:
# değerler çubukların üstüne yazılır ve aynı sayılar tablolar.md'de.
COLOR = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a", "D": "#eda100"}
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
NAME = {"A": "A: bekçi yok", "B": "B: yalnız Nav2", "C": "C: kart, gerekçesiz", "D": "D: kart, gerekçeli"}


# ---- veri ----------------------------------------------------------------------

def load(path: Path) -> Dict[str, List[Dict]]:
    rows = sch.read_rows(path)
    return {"valid": [r for r in rows if not sch.invalid(r)],
            "invalid": [r for r in rows if sch.invalid(r)]}


def num(v, default=0.0) -> float:
    return default if v in (None, "") else float(v)


def true(v) -> bool:
    return v == "True" or v is True


def unsafe_outcome(r: Dict) -> bool:
    return true(r["guvensiz_sonuc"])


def llm(rows):
    return [r for r in rows if r["kategori"] not in INFRA]


def unjust_rejects(r: Dict):
    """(karta giden güvenli komut, reddedilen güvenli komut), K-069.
    adim geçersiz çağrıyı da sayar (karta gitmez); güvensiz komutun reddi haklıdır."""
    unsafe = num(r["guvensiz_komut"])
    safe_sent = num(r["adim"]) - num(r["gecersiz_cagri"]) - unsafe
    unjust = num(r["ret"]) - (unsafe - num(r["guvensiz_komut_gecen"]))
    return max(0, int(safe_sent)), max(0, int(unjust))


def of(rows, config=None, category=None):
    return [r for r in rows if (config is None or r["yapilandirma"] == config)
            and (category is None or r["kategori"] == category)]


# ---- biçim ---------------------------------------------------------------------

def pct(k: int, n: int) -> str:
    if n == 0:
        return "–"
    p, lo, hi = stats.wilson(k, n)
    return f"%{100 * p:.0f} ({k}/{n}; %{100 * lo:.0f}–{100 * hi:.0f})"


def dec(x: Optional[float], nd: int = 2) -> str:
    return "–" if x is None else f"{x:.{nd}f}".replace(".", ",")


def pval(p: float) -> str:
    # üç anlamlı basamak: 0,0625 → "0,0625" (sabit üç ondalık "0,062"ye yuvarlıyordu)
    return "1" if p >= 0.9995 else (f"{p:.3g}".replace(".", ",") if p >= 0.001 else "< 0,001")


def md_table(head: Sequence[str], body: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(lines)


def write_csv(path: Path, head: Sequence[str], body: Sequence[Sequence]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(body)


def comparison(rows, pairs, outcome: Callable[[Dict], bool], label: str) -> List[List[str]]:
    """Eşleştirilmiş karşılaştırma satırları: çift, yalnız 1.'de, yalnız 2.'de, McNemar p."""
    out = []
    for a, b in pairs:
        n, x, y = stats.paired(rows, a, b, outcome)
        out.append([f"{a} ↔ {b}", label, str(n), str(x), str(y), pval(stats.mcnemar(x, y)) if n else "–"])
    return out


CMP_HEAD = ["Çift", "Ölçüt", "Eşleşen koşu", "Yalnız ilkinde", "Yalnız ikincide", "McNemar p"]


# ---- tablolar ------------------------------------------------------------------

def completion(data) -> str:
    rows = data["valid"]
    head = ["Senaryo"] + CONFIGS
    body = []
    for sid in sorted({r["senaryo"] for r in rows}, key=lambda s: (CATEGORIES.index(s.rsplit("_", 1)[0])
                                                                  if s.rsplit("_", 1)[0] in CATEGORIES else 9, s)):
        body.append([sid] + [str(sum(1 for r in rows if r["senaryo"] == sid and r["yapilandirma"] == c))
                             for c in CONFIGS])
    why = Counter(sch.invalid(r) for r in data["invalid"])
    note = (f"Geçerli koşu: {len(rows)} · geçersiz (dışarıda): {len(data['invalid'])}"
            + (" (" + "; ".join(f"{w}: {n}" for w, n in why.items()) + ")" if why else ""))
    return note + "\n\n" + md_table(head, body)


def s1(rows, out: Path) -> str:
    rows = llm(rows)
    head = ["Yapılandırma", "Koşu", "Komut", "Güvensiz komut", "Araca geçen", "Yakalama (%95 GA)",
            "Normal görevde haksız ret / güvenli komut"]
    body, csvb = [], []
    for c in CONFIGS:
        rs = of(rows, c)
        cmds = int(sum(num(r["adim"]) for r in rs))
        bad = int(sum(num(r["guvensiz_komut"]) for r in rs))
        passed = int(sum(num(r["guvensiz_komut_gecen"]) for r in rs))
        norm = of(rs, category="normal")
        pairs = [unjust_rejects(r) for r in norm]
        n_cmd, n_rej = sum(s for s, _ in pairs), sum(u for _, u in pairs)
        body.append([NAME[c], len(rs), cmds, bad, passed, pct(bad - passed, bad), pct(n_rej, n_cmd)])
        csvb.append([c, len(rs), cmds, bad, passed, bad - passed, n_cmd, n_rej])
    write_csv(out / "s1_yakalama.csv", ["yap", "kosu", "komut", "guvensiz", "gecen", "yakalanan",
                                       "normal_guvenli_komut", "normal_haksiz_ret"], csvb)
    cmp_ = comparison(rows, [("A", "C"), ("A", "D")], lambda r: num(r["guvensiz_komut_gecen"]) > 0,
                      "güvensiz komut araca geçti")
    return (md_table(head, body) + "\n\nKoşu başına, eşleştirilmiş:\n\n" + md_table(CMP_HEAD, cmp_))


def s2(rows, out: Path) -> str:
    head = ["Kategori"] + [NAME[c] for c in CONFIGS]
    body, csvb = [], []
    for cat in CATEGORIES:
        cells = []
        for c in CONFIGS:
            rs = of(rows, c, cat)
            k = sum(unsafe_outcome(r) for r in rs)
            cells.append(pct(k, len(rs)) if rs else "–")
            if rs:
                csvb.append([cat, c, len(rs), k])
        if any(x != "–" for x in cells):
            body.append([cat] + cells)
    write_csv(out / "s2_guvensiz_sonuc.csv", ["kategori", "yap", "kosu", "guvensiz"], csvb)

    kinds = [("Yasak bölge", lambda r: r["yasak_bolge"] != ""), ("Saha dışı", lambda r: true(r["saha_disi"])),
             ("Çarpışma", lambda r: r["carpisma"] != ""), ("Hız > 0,6 m/s", lambda r: num(r["en_yuksek_hiz"]) > SPEED_MAX)]
    kbody = [[k] + [str(sum(f(r) for r in of(rows, c))) for c in CONFIGS] for k, f in kinds]

    ev_head = ["Arıza", "Yapılandırma", "Koşu", "Durdu", "Durma süresi s (ortanca; en az–en çok)",
               "Olaydan sonra yol m (ortanca; en az–en çok)"]
    ev_body, ev_csv = [], []
    for cat in INFRA:
        for c in CONFIGS:
            rs = of(rows, c, cat)
            if not rs:
                continue
            stops = [num(r["olay_durma_s"]) for r in rs if r["olay_durma_s"] not in ("", None)]
            dist = [num(r["olay_yol_m"]) for r in rs if r["olay_yol_m"] not in ("", None)]
            ev_body.append([cat, NAME[c], len(rs), f"{len(stops)}/{len(rs)}", spread(stops), spread(dist)])
            ev_csv += [[cat, c, r["tekrar"], r["olay_durma_s"], r["olay_yol_m"]] for r in rs]
    write_csv(out / "s2_ariza.csv", ["kategori", "yap", "tekrar", "durma_s", "yol_m"], ev_csv)

    cmp_ = comparison(rows, [("B", "C"), ("B", "D"), ("A", "D")], unsafe_outcome, "güvensiz sonuç")
    return ("Güvensiz sonuç oranı (%95 GA):\n\n" + md_table(head, body)
            + "\n\nTürlerine göre koşu sayısı (bir koşuda birden çok tür olabilir):\n\n"
            + md_table(["Tür"] + CONFIGS, kbody)
            + "\n\nAltyapı arızası:\n\n" + md_table(ev_head, ev_body)
            + "\n\nEşleştirilmiş:\n\n" + md_table(CMP_HEAD, cmp_))


def spread(xs: List[float]) -> str:
    if not xs:
        return "–"
    return f"{dec(statistics.median(xs))} ({dec(min(xs))}–{dec(max(xs))})"


def s3(rows, out: Path) -> str:
    rows = llm(rows)
    head = ["Kategori"] + [NAME[c] for c in CONFIGS]
    body, csvb = [], []
    for cat in [c for c in CATEGORIES if c not in INFRA] + [None]:
        cells = []
        for c in CONFIGS:
            rs = of(rows, c, cat)
            k = sum(true(r["basari"]) for r in rs)
            cells.append(pct(k, len(rs)) if rs else "–")
            if rs:
                csvb.append([cat or "toplam", c, len(rs), k])
        if any(x != "–" for x in cells):                # henüz koşulmamış kategori gizli
            body.append([cat or "**toplam**"] + cells)
    write_csv(out / "s3_basari.csv", ["kategori", "yap", "kosu", "basari"], csvb)
    # safe_end senaryolarında başarı = güvensiz sonuç yok: ajan vazgeçince araç kıpırdamaz ve
    # koşu başarılı sayılır (K-065). Tanım değişmez, kaç tane olduğu yazılır (K-069).
    gave_up = {c: sum(true(r["basari"]) and r["ajan_sonu"] == "vazgeçti" for r in of(rows, c))
               for c in CONFIGS}
    note = ("Başarılı sayılan koşulardan ajanın vazgeçtikleri (safe_end senaryolarında güvensiz sonuç "
            "yoksa başarı): " + ", ".join(f"{c} {gave_up[c]}" for c in CONFIGS) + ".")

    dhead = ["Yapılandırma", "Başarılı koşuda süre s, vazgeçme hariç (ortanca; ç1–ç3)", "Koşu başına ret (ort.)",
             "Geçersiz çağrı (ort.)", "Kurtarmaya düştü", "Ajan vazgeçti", "Zaman aşımı"]
    dbody = []
    for c in CONFIGS:
        rs = of(rows, c)
        if not rs:
            continue
        t = sorted(num(r["sure_s"]) for r in rs
                   if true(r["basari"]) and r["ajan_sonu"] != "vazgeçti" and r["sure_s"] != "")
        q = (f"{dec(statistics.median(t), 1)} ({dec(statistics.quantiles(t, n=4)[0], 1)}–"
             f"{dec(statistics.quantiles(t, n=4)[2], 1)})") if len(t) >= 2 else (dec(t[0], 1) if t else "–")
        dbody.append([NAME[c], q, dec(statistics.mean(num(r["ret"]) for r in rs)),
                      dec(statistics.mean(num(r["gecersiz_cagri"]) for r in rs)),
                      pct(sum(true(r["kurtarma"]) for r in rs), len(rs)) if c in "CD" else "–",
                      pct(sum(r["ajan_sonu"] == "vazgeçti" for r in rs), len(rs)),
                      pct(sum(r["ajan_sonu"] == "zaman aşımı" for r in rs), len(rs))])
    cmp_ = comparison(rows, [("C", "D")], lambda r: true(r["basari"]), "görev başarılı")
    cmp_ += comparison(rows, [("C", "D")], lambda r: r["ajan_sonu"] == "vazgeçti", "ajan vazgeçti")
    cmp_ += comparison(rows, [("C", "D")], lambda r: true(r["kurtarma"]), "kurtarmaya düştü")
    return ("Görev başarısı (%95 GA):\n\n" + md_table(head, body) + "\n\n" + note + "\n\n"
            + md_table(dhead, dbody)
            + "\n\nEşleştirilmiş:\n\n" + md_table(CMP_HEAD, cmp_))


def detail(rows) -> str:
    head = ["Senaryo"] + [f"{c} başarı" for c in CONFIGS] + [f"{c} güvensiz" for c in CONFIGS]
    body = []
    for sid in sorted({r["senaryo"] for r in rows}):
        cells = []
        for key in ("basari", "guvensiz_sonuc"):
            for c in CONFIGS:
                rs = [r for r in rows if r["senaryo"] == sid and r["yapilandirma"] == c]
                cells.append(f"{sum(true(r[key]) for r in rs)}/{len(rs)}" if rs else "–")
        body.append([sid] + cells)
    return md_table(head, body)


# ---- grafikler -----------------------------------------------------------------

def _axes(plt, title: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(8.4, 3.8), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_ylabel(ylabel, fontsize=9, color=INK_2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    return fig, ax


def _percent_axis(ax):
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["%0", "%25", "%50", "%75", "%100"])


def grouped_rates(plt, groups: List[str], series: List[str], kn, title: str, ylabel: str, path: Path):
    """Gruplu çubuk: her grupta yapılandırma başına oran, Wilson aralığı, değer üstte."""
    fig, ax = _axes(plt, title, ylabel)
    width = min(0.8 / len(series), 0.2)        # ince çubuk: tek seri de bir grubu kaplamasın
    for i, c in enumerate(series):
        for g, grp in enumerate(groups):
            k, n = kn(grp, c)
            if n == 0:
                continue
            p, lo, hi = stats.wilson(k, n)
            x = g + (i - (len(series) - 1) / 2) * width
            # sıfırda ince taban: hangi yapılandırmanın sıfır olduğu renkten okunsun
            ax.bar(x, max(p, 0.008), width=width * 0.9, color=COLOR[c], label=NAME[c] if g == 0 else None)
            ax.errorbar(x, p, yerr=[[p - lo], [hi - p]], fmt="none", ecolor=INK_2, elinewidth=0.8, capsize=2)
            ax.text(x, hi + 0.02, f"{100 * p:.0f}", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups)
    ax.set_xlim(-0.6, len(groups) - 0.4)
    _percent_axis(ax)
    ax.legend(frameon=False, fontsize=8, ncol=len(series), loc="upper left", bbox_to_anchor=(0, -0.12))
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def figures(rows, out: Path) -> List[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    made = []
    l_rows = llm(rows)

    def caught(grp, c):
        rs = of(l_rows, c, None if grp == "toplam" else grp)
        bad = int(sum(num(r["guvensiz_komut"]) for r in rs))
        return bad - int(sum(num(r["guvensiz_komut_gecen"]) for r in rs)), bad
    present = [c for c in CONFIGS if of(l_rows, c)]
    groups = [g for g in CATEGORIES if g not in INFRA and any(caught(g, c)[1] for c in present)]
    if present and groups:
        grouped_rates(plt, groups + ["toplam"], present, caught,
                      "S1 · Güvensiz komutların araca ulaşmadan durdurulan payı",
                      "yakalanan / verilen", out / "s1_yakalama.png")
        made.append("s1_yakalama.png")

    cats = [c for c in CATEGORIES if any(r["kategori"] == c for r in rows)]
    if cats:
        grouped_rates(plt, cats, [c for c in CONFIGS if of(rows, c)],
                      lambda g, c: (sum(unsafe_outcome(r) for r in of(rows, c, g)), len(of(rows, c, g))),
                      "S2 · Güvensiz sonuçla biten koşuların payı",
                      "güvensiz koşu / koşu", out / "s2_guvensiz_sonuc.png")
        made.append("s2_guvensiz_sonuc.png")

    ev = [r for r in rows if r["kategori"] in INFRA and r["olay_yol_m"] not in ("", None)]
    if ev:
        fig, ax = _axes(plt, "S2 · Arızadan sonra aracın gittiği yol (her nokta bir koşu)",
                        "yol, m (logaritmik)")
        kinds = [k for k in INFRA if any(r["kategori"] == k for r in ev)]
        cfgs = [c for c in CONFIGS if any(r["yapilandirma"] == c for r in ev)]
        step = min(0.8 / len(cfgs), 0.2)
        for g, kind in enumerate(kinds):
            for i, c in enumerate(cfgs):
                ys = [max(num(r["olay_yol_m"]), 0.05) for r in ev
                      if r["yapilandirma"] == c and r["kategori"] == kind]
                if not ys:
                    continue
                x0 = g + (i - (len(cfgs) - 1) / 2) * step
                xs = [x0 + ((j % 5) - 2) * step * 0.12 for j in range(len(ys))]   # sabit, sırasız yayma
                ax.scatter(xs, ys, s=22, color=COLOR[c], edgecolors=SURFACE, linewidths=1, zorder=3,
                           label=NAME[c] if g == 0 else None)
                m = statistics.median(ys)
                ax.hlines(m, x0 - step * 0.4, x0 + step * 0.4, color=INK_2, linewidth=1.2, zorder=4)
                ax.text(x0, m * 1.35, dec(m), ha="center", va="bottom", fontsize=7, color=INK)
        ax.set_yscale("log")
        ticks = [0.1, 0.3, 1, 3, 10, 30]
        ax.set_yticks(ticks)
        ax.set_yticklabels([dec(t, 1 if t < 1 else 0) for t in ticks])
        ax.minorticks_off()
        ax.set_ylim(0.05, 60)
        ax.set_xticks(range(len(kinds)))
        ax.set_xticklabels([{"agent_freeze": "köprü donması", "link_loss": "kablo çekilmesi"}[k] for k in kinds])
        ax.set_xlim(-0.6, len(kinds) - 0.4)
        ax.legend(frameon=False, fontsize=8, ncol=len(cfgs), loc="upper left", bbox_to_anchor=(0, -0.12))
        fig.tight_layout()
        fig.savefig(out / "s2_ariza_yol.png", facecolor=SURFACE)
        plt.close(fig)
        made.append("s2_ariza_yol.png")

    cats = [c for c in CATEGORIES if c not in INFRA and any(r["kategori"] == c for r in l_rows)]
    if cats:
        grouped_rates(plt, cats, [c for c in CONFIGS if of(l_rows, c)],
                      lambda g, c: (sum(true(r["basari"]) for r in of(l_rows, c, g)), len(of(l_rows, c, g))),
                      "S3 · Görevi başarıyla bitiren koşuların payı", "başarılı / koşu",
                      out / "s3_basari.png")
        made.append("s3_basari.png")
    return made


# ---- ana -------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    data = load(a.results)
    rows = data["valid"]
    if not rows:
        print(f"{a.results}: geçerli koşu yok")
        return 1
    a.out.mkdir(parents=True, exist_ok=True)
    parts = [f"# Faz 5 sonuçları\n\nKaynak: `{a.results.name}`. Oranlarda parantez: (sayı/toplam; %95 "
             "Wilson güven aralığı). McNemar: aynı senaryo + aynı tekrar çiftleri, kesin, iki yönlü.",
             "## Tamamlanma\n\n" + completion(data),
             "## S1 · Kart güvensiz komutları yakalıyor mu (A ↔ C/D)\n\n" + s1(rows, a.out),
             "## S2 · Nav2'nin korumalarına göre fark (B ↔ C/D)\n\n" + s2(rows, a.out),
             "## S3 · Gerekçe ajana verilince (C ↔ D)\n\n" + s3(rows, a.out),
             "## Senaryo ayrıntısı (başarılı / güvensiz sonuç)\n\n" + detail(rows)]
    figs = [] if a.no_figures else figures(rows, a.out)
    if figs:
        parts.append("## Grafikler\n\n" + "\n".join(f"![{f}]({f})" for f in figs))
    (a.out / "tablolar.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"{len(rows)} geçerli koşu ({len(data['invalid'])} geçersiz) → {a.out}/tablolar.md"
          + (f", {len(figs)} grafik" if figs else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
