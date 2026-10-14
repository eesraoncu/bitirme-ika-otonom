#!/usr/bin/env python3
"""Model seçim testi (Faz 4.0): hangi yerel model araçlarımızı Türkçe görevle doğru çağırıyor.

Kullanım (Ollama servisi açık, modeller indirilmiş):
    python3 tools/llm_select_bench.py                                  # sıcaklık 0, tek koşu
    python3 tools/llm_select_bench.py --temperature 0.7 --seeds 5      # kararlılık
    python3 tools/llm_select_bench.py granite4.1:3b -v                 # tek model, hataları yaz

ROS'a, karta ve simülasyona dokunmaz; yalnız Ollama'nın HTTP arayüzüyle konuşur.
Her görev cümlesi modele araç tanımlarıyla gönderilir, modelin İLK araç çağrısı
beklenenle karşılaştırılır. Her cümle her seed'le bir kez sorulur (seed 42, 43, …);
sıcaklık 0'da seed'ler aynı cevabı verir, > 0'da kararlılığı ölçer. Cümleler kategorili
(yer, koordinat, birim, dur, bileşik, ret); tablo kategori başına doğruyu da verir.
"GPU payı" /api/ps'ten: modelin VRAM'deki oranı.

Araç tanımları ve sistem istemi ajanın kendisinden (ros2_ws/src/llm_agent/agent_core.py).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_site as gs   # noqa: E402

OLLAMA = "http://localhost:11434"
CANDIDATES = ["granite4.1:3b", "qwen3.5:4b"]   # elenen ve silinen: phi4-mini, qwen3.5:2b (K-045)
NUM_CTX = 4096
FIRST_SEED = 42
TIMEOUT_S = 300

SITE = gs.load_site()

# Sistem istemi, araç tanımları ve yer adları ajanın kendisinden (tek kaynak, Faz 4.3):
# ölçülen, ajanın gerçekten kullandığıdır.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "llm_agent"))
import agent_core as ac  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "guard_bridge"))
import convert as cv  # noqa: E402

PLACES = sorted(ac.places_from_site(SITE))   # güvenli noktalar + places (K-044)
SYSTEM = ac.SYSTEM
TOOLS = ac.tool_definitions(PLACES)


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _near(v, want, tol=0.01):
    n = _num(v)
    return n is not None and abs(n - want) <= tol


def go_place(name):
    return lambda a: a.get("yer") == name


def go_xy(x, y):
    return lambda a: _near(a.get("x"), x) and _near(a.get("y"), y)


def _rejected(call, verdict):
    """Reddedilmiş bir çağrıyı ve kartın gerekçesini konuşma geçmişi olarak kur."""
    name, args = call
    return [
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": name, "arguments": args}}]},
        {"role": "tool", "tool_name": name,
         "content": verdict if isinstance(verdict, str) else json.dumps(verdict, ensure_ascii=False)},
    ]


def wait_s(s):
    return lambda a: _near(a.get("sure_s"), s)


def speed(v):
    return lambda a: _near(a.get("deger_mps"), v)


def geofence_case(cid, text, x, y, reason):
    """Hedefi reddedilmiş bir 'git'; ipucu kartın hesabıyla (gen_site.nearest_safe) bulunur.
    Gerekçe, ajanın gerçekte gördüğü köprü metni (convert.feedback_text, D, K-050)."""
    safe = SITE["safe"]
    hint = gs.nearest_safe(list(safe.values()), SITE["home"], (round(x * 100), round(y * 100)))
    name = next(n for n, p in safe.items() if p == hint)
    hx, hy = hint[0] / 100, hint[1] / 100
    verdict = cv.feedback_text("REJECTED", "GEOFENCE", reason, 0, 0, 0, hint[0], hint[1],
                               full=True, safe_points=safe)
    return ("ret", cid, text, _rejected(("git", {"x": x, "y": y}), verdict),
            "git", lambda a: a.get("yer") == name or go_xy(hx, hy)(a))


def limit_case(cid, text, v):
    verdict = cv.feedback_text("REJECTED", "LIMIT", "ABOVE_MAX", round(v * 1000), 1, 600, 0, 0,
                               full=True)
    return ("ret", cid, text, _rejected(("hiz_siniri", {"deger_mps": v}), verdict),
            "hiz_siniri", lambda a: 0 < (_num(a.get("deger_mps")) or 0) <= 0.6)


# (kategori, kimlik, kullanıcı cümlesi, ek geçmiş, beklenen araç, argüman denetimi)
CASES = [
    ("yer", "kapi_onu", "Kapı önüne git.", [], "git", go_place("kapi_onu")),
    ("yer", "kapiya", "Kapıya git.", [], "git", go_place("kapi_onu")),
    ("yer", "konteyner_arka", "Konteynerin arkasına git.", [], "git", go_place("konteyner_arkasi")),
    ("yer", "konteyner_on", "Konteynerin önüne git.", [], "git", go_place("konteyner_onu")),
    ("yer", "baslangic", "Başlangıç noktasına dön.", [], "git", go_place("baslangic")),
    ("yer", "geldigin_yer", "Geldiğin yere geri dön.", [], "git", go_place("baslangic")),
    ("yer", "kuzeybati", "Sahanın kuzeybatısındaki noktaya git.", [], "git", go_place("kuzeybati")),
    ("koordinat", "xy", "(8, 2) noktasına git.", [], "git", go_xy(8, 2)),
    ("koordinat", "ondalik", "x 12,5 y -3 noktasına git.", [], "git", go_xy(12.5, -3)),
    ("koordinat", "eksi_yazili", "x eksi 1, y 4 noktasına git.", [], "git", go_xy(-1, 4)),
    ("koordinat", "esittir", "Hedef: x=20, y=-2,5.", [], "git", go_xy(20, -2.5)),
    ("birim", "bekle_30s", "Burada 30 saniye bekle.", [], "bekle", wait_s(30)),
    ("birim", "bekle_2dk", "İki dakika bekle.", [], "bekle", wait_s(120)),
    ("birim", "bekle_yarim", "Yarım dakika bekle.", [], "bekle", wait_s(30)),
    ("birim", "bekle_1_5dk", "Bir buçuk dakika bekle.", [], "bekle", wait_s(90)),
    ("birim", "hiz_mps", "Hızını saniyede 0,3 metreye düşür.", [], "hiz_siniri", speed(0.3)),
    ("birim", "hiz_cm", "Hızı saniyede 30 santimetreyle sınırla.", [], "hiz_siniri", speed(0.3)),
    ("birim", "hiz_limit_disi", "Hızı 2 m/s yap.", [], "hiz_siniri", speed(2.0)),
    ("dur", "dur", "Dur!", [], "dur", lambda a: True),
    ("dur", "durdur", "Hemen aracı durdur.", [], "dur", lambda a: True),
    ("bilesik", "git_bekle", "Kapı önüne git, orada 30 saniye bekle.", [],
     "git", go_place("kapi_onu")),
    ("bilesik", "hiz_git", "Önce hızını 0,2 m/s'ye düşür, sonra konteynerin arkasına git.", [],
     "hiz_siniri", speed(0.2)),
    ("bilesik", "bekle_don", "Bir dakika bekle, sonra başlangıca dön.", [], "bekle", wait_s(60)),
    geofence_case("kazi", "Kazı alanının ortasına, (14, 0) noktasına git.", 14, 0,
                  "GOAL_IN_FORBIDDEN"),
    geofence_case("personel", "(4, -7) noktasına git.", 4, -7, "GOAL_IN_FORBIDDEN"),
    geofence_case("yakit", "Yakıt alanına, (21, -6) noktasına git.", 21, -6, "GOAL_IN_FORBIDDEN"),
    geofence_case("disari_bati", "(-6, 8) noktasına git.", -6, 8, "GOAL_OUTSIDE_ALLOWED"),
    geofence_case("disari_kuzey", "x 10, y 12 noktasına git.", 10, 12, "GOAL_OUTSIDE_ALLOWED"),
    limit_case("hiz_2", "Hızı 2 m/s yap.", 2.0),
    limit_case("hiz_1", "Saniyede 1 metreyle git.", 1.0),
    limit_case("hiz_08", "Hız sınırını 0,8 m/s yap.", 0.8),
]
CATEGORIES = list(dict.fromkeys(c[0] for c in CASES))


def capabilities(model):
    r = requests.post(f"{OLLAMA}/api/show", json={"model": model}, timeout=30)
    r.raise_for_status()
    return r.json().get("capabilities", [])


def gpu_share(model):
    """Yüklü modelin VRAM'de duran oranı (1,0 = tamamı GPU'da)."""
    full = model if ":" in model else f"{model}:latest"   # /api/ps etiketi hep yazar
    for m in requests.get(f"{OLLAMA}/api/ps", timeout=10).json().get("models", []):
        if m.get("name") == full:
            return m["size_vram"] / m["size"] if m.get("size") else None
    return None


def ask(model, think_off, history, text, options):
    body = {"model": model, "stream": False, "options": options, "tools": TOOLS,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": text}, *history]}
    if think_off:
        body["think"] = False
    t0 = time.monotonic()
    r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=TIMEOUT_S)
    elapsed = time.monotonic() - t0
    r.raise_for_status()
    return r.json()["message"], elapsed


def grade(msg, want_tool, check):
    """'dogru', 'yanlis_arguman', 'yanlis_arac' ya da 'cagri_yok'."""
    calls = msg.get("tool_calls") or []
    if not calls:
        return "cagri_yok", None
    fn = calls[0]["function"]
    args = fn.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return "cagri_yok", fn
    if fn.get("name") != want_tool:
        return "yanlis_arac", fn
    return ("dogru" if check(args) else "yanlis_arguman"), fn


def run_model(model, temperature, seeds, verbose):
    think_off = "thinking" in capabilities(model)
    opts = [{"temperature": temperature, "seed": FIRST_SEED + k, "num_ctx": NUM_CTX}
            for k in range(seeds)]
    ask(model, think_off, [], "Dur!", opts[0])         # ısınma: model belleğe yüklenir
    share = gpu_share(model)
    counts = {"dogru": 0, "yanlis_arguman": 0, "yanlis_arac": 0, "cagri_yok": 0}
    per_cat = {c: [0, 0] for c in CATEGORIES}          # kategori → [doğru, toplam]
    times, unstable = [], []
    for cat, cid, text, history, want_tool, check in CASES:
        seen = set()
        for o in opts:
            msg, dt = ask(model, think_off, history, text, o)
            verdict, fn = grade(msg, want_tool, check)
            counts[verdict] += 1
            per_cat[cat][0] += verdict == "dogru"
            per_cat[cat][1] += 1
            times.append(dt)
            seen.add(json.dumps(fn, sort_keys=True, ensure_ascii=False))
            if verbose and verdict != "dogru":
                shown = fn or msg.get("content", "")[:80]
                print(f"  [{model}] {cat}/{cid} seed {o['seed']}: {verdict} → {shown!r}")
        if len(seen) > 1:
            unstable.append(cid)
    return {"model": model, "gpu": share, "total": sum(counts.values()), "counts": counts,
            "per_cat": per_cat, "median_s": statistics.median(times), "max_s": max(times),
            "unstable": unstable}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("models", nargs="*", default=CANDIDATES)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seeds", type=int, default=1, help=f"seed {FIRST_SEED}, {FIRST_SEED + 1}, …")
    ap.add_argument("-v", "--verbose", action="store_true", help="hatalı cevapları yazdır")
    a = ap.parse_args()

    print(f"{len(CASES)} cümle × {a.seeds} seed, sıcaklık {a.temperature}, num_ctx {NUM_CTX}, "
          f"yerler {PLACES}\n")
    rows = []
    for model in a.models:
        print(f"→ {model} …", flush=True)
        rows.append(run_model(model, a.temperature, a.seeds, a.verbose))

    print(f"\n{'model':<15} {'doğru':>8} {'yanlış arg':>10} {'yanlış araç':>11} "
          f"{'çağrı yok':>9} {'medyan s':>8} {'en çok s':>8} {'GPU':>5}")
    for r in rows:
        c, n = r["counts"], r["total"]
        gpu = f"{r['gpu']:.0%}" if r["gpu"] is not None else "?"
        print(f"{r['model']:<15} {c['dogru']:>4}/{n:<3} {c['yanlis_arguman']:>10} "
              f"{c['yanlis_arac']:>11} {c['cagri_yok']:>9} {r['median_s']:>8.2f} "
              f"{r['max_s']:>8.2f} {gpu:>5}")

    print(f"\n{'model':<15} " + " ".join(f"{c:>10}" for c in CATEGORIES) + "  kararsız")
    for r in rows:
        cells = " ".join(f"{d:>6}/{t:<3}" for d, t in (r["per_cat"][c] for c in CATEGORIES))
        print(f"{r['model']:<15} {cells}  {', '.join(r['unstable']) or '-'}")


if __name__ == "__main__":
    main()
