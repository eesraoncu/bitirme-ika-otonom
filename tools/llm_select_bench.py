#!/usr/bin/env python3
"""Model seçim testi (Faz 4.0): hangi yerel model araçlarımızı Türkçe görevle doğru çağırıyor.

Kullanım (Ollama servisi açık, modeller indirilmiş):
    python3 tools/llm_select_bench.py                         # varsayılan dört aday
    python3 tools/llm_select_bench.py qwen3.5:4b --repeat 5   # tek model, 5 tekrar

ROS'a, karta ve simülasyona dokunmaz; yalnız Ollama'nın HTTP arayüzüyle konuşur.
Her görev cümlesi modele araç tanımlarıyla gönderilir, modelin İLK araç çağrısı
beklenenle karşılaştırılır. Sıcaklık 0 ve seed sabit: tekrarlar aynı cevabı vermeli,
süre ortancası tekrarlardan alınır. "GPU payı" /api/ps'ten: modelin VRAM'deki oranı.

Araç tanımları burada TASLAK. 4.3'te ajana (llm_agent) taşınır, bu betik oradan okur.
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
CANDIDATES = ["qwen3.5:4b", "qwen3.5:2b", "granite4.1:3b", "phi4-mini"]
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096}
TIMEOUT_S = 300

PLACES = list(gs.load_site()["safe"])   # adlı yerler ika_saha.yaml'dan (K-044)

SYSTEM = (
    "Sen bir insansız kara aracını (İKA) yöneten görev ajanısın. Kullanıcının Türkçe "
    "talimatını yalnızca verilen araçları çağırarak yerine getir. Yer adı verilmişse "
    "'yer' alanını kullan, koordinat verilmişse 'x' ve 'y' alanlarını (metre) kullan. "
    "Bir komut reddedilirse gelen gerekçeyi okuyup düzeltilmiş yeni bir komut ver."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "git",
        "description": "Aracı bir hedefe gönder. Ya 'yer' ya da 'x' ile 'y' verilir.",
        "parameters": {"type": "object", "properties": {
            "yer": {"type": "string", "enum": PLACES, "description": "Kayıtlı yerin adı"},
            "x": {"type": "number", "description": "Hedefin x koordinatı, metre"},
            "y": {"type": "number", "description": "Hedefin y koordinatı, metre"},
        }},
    }},
    {"type": "function", "function": {
        "name": "bekle",
        "description": "Olduğun yerde belirtilen süre bekle.",
        "parameters": {"type": "object", "required": ["sure_s"], "properties": {
            "sure_s": {"type": "number", "description": "Bekleme süresi, saniye"},
        }},
    }},
    {"type": "function", "function": {
        "name": "hiz_siniri",
        "description": "Aracın en yüksek hızını sınırla.",
        "parameters": {"type": "object", "required": ["deger_mps"], "properties": {
            "deger_mps": {"type": "number", "description": "Hız sınırı, m/s"},
        }},
    }},
    {"type": "function", "function": {
        "name": "dur",
        "description": "Aracı hemen durdur.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


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
        {"role": "tool", "tool_name": name, "content": json.dumps(verdict, ensure_ascii=False)},
    ]


# (kimlik, kullanıcı cümlesi, ek geçmiş, beklenen araç, argüman denetimi)
CASES = [
    ("yer_kapi", "Kapı önüne git.", [], "git", go_place("kapi_onu")),
    ("yer_konteyner", "Konteynerin arkasına git.", [], "git", go_place("konteyner_arkasi")),
    ("yer_baslangic", "Başlangıç noktasına dön.", [], "git", go_place("baslangic")),
    ("yer_kuzeybati", "Sahanın kuzeybatısındaki noktaya git.", [], "git", go_place("kuzeybati")),
    ("koordinat", "(8, 2) noktasına git.", [], "git", go_xy(8, 2)),
    ("koordinat_ondalik", "x 12,5 y -3 noktasına git.", [], "git", go_xy(12.5, -3)),
    ("bekle", "Burada 30 saniye bekle.", [], "bekle", lambda a: _near(a.get("sure_s"), 30)),
    ("bekle_dakika", "İki dakika bekle.", [], "bekle", lambda a: _near(a.get("sure_s"), 120)),
    ("hiz", "Hızını saniyede 0,3 metreye düşür.", [], "hiz_siniri",
     lambda a: _near(a.get("deger_mps"), 0.3)),
    ("hiz_limit_disi", "Hızı 2 m/s yap.", [], "hiz_siniri",
     lambda a: _near(a.get("deger_mps"), 2.0)),
    ("dur", "Dur!", [], "dur", lambda a: True),
    ("bilesik", "Kapı önüne git, orada 30 saniye bekle.", [], "git", go_place("kapi_onu")),
    ("ret_cografi", "Kazı alanının ortasına, (14, 0) noktasına git.",
     _rejected(("git", {"x": 14, "y": 0}),
               {"karar": "REDDEDILDI", "kural": "GEOFENCE", "neden": "GOAL_IN_FORBIDDEN",
                "en_yakin_guvenli_nokta": "konteyner_onu"}),
     "git", lambda a: a.get("yer") == "konteyner_onu" or go_xy(8, 2)(a)),
    ("ret_hiz", "Hızı 2 m/s yap.",
     _rejected(("hiz_siniri", {"deger_mps": 2.0}),
               {"karar": "REDDEDILDI", "kural": "LIMIT", "istenen_mps": 2.0,
                "izinli_aralik_mps": [0, 0.6]}),
     "hiz_siniri", lambda a: (_num(a.get("deger_mps")) or 0) > 0
                             and (_num(a.get("deger_mps")) or 0) <= 0.6),
]


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


def ask(model, think_off, history, text):
    body = {"model": model, "stream": False, "options": OPTIONS, "tools": TOOLS,
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


def run_model(model, repeat, verbose):
    think_off = "thinking" in capabilities(model)
    ask(model, think_off, [], "Dur!")                 # ısınma: model belleğe yüklenir
    share = gpu_share(model)
    counts = {"dogru": 0, "yanlis_arguman": 0, "yanlis_arac": 0, "cagri_yok": 0}
    times, unstable = [], []
    for cid, text, history, want_tool, check in CASES:
        seen = set()
        for _ in range(repeat):
            msg, dt = ask(model, think_off, history, text)
            verdict, fn = grade(msg, want_tool, check)
            counts[verdict] += 1
            times.append(dt)
            seen.add(json.dumps(fn, sort_keys=True, ensure_ascii=False))
            if verbose and verdict != "dogru":
                print(f"  [{model}] {cid}: {verdict} → {fn or msg.get('content', '')[:80]!r}")
        if len(seen) > 1:
            unstable.append(cid)
    total = sum(counts.values())
    return {"model": model, "think_off": think_off, "gpu": share, "total": total,
            "counts": counts, "median_s": statistics.median(times),
            "max_s": max(times), "unstable": unstable}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("models", nargs="*", default=CANDIDATES)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("-v", "--verbose", action="store_true", help="hatalı cevapları yazdır")
    a = ap.parse_args()

    print(f"{len(CASES)} cümle × {a.repeat} tekrar, seçenekler {OPTIONS}, yerler {PLACES}\n")
    rows = []
    for model in a.models:
        print(f"→ {model} …", flush=True)
        rows.append(run_model(model, a.repeat, a.verbose))

    print(f"\n{'model':<15} {'doğru':>7} {'yanlış arg':>10} {'yanlış araç':>11} "
          f"{'çağrı yok':>9} {'medyan s':>8} {'en çok s':>8} {'GPU':>5}  kararsız")
    for r in rows:
        c, n = r["counts"], r["total"]
        gpu = f"{r['gpu']:.0%}" if r["gpu"] is not None else "?"
        print(f"{r['model']:<15} {c['dogru']:>3}/{n:<3} {c['yanlis_arguman']:>10} "
              f"{c['yanlis_arac']:>11} {c['cagri_yok']:>9} {r['median_s']:>8.2f} "
              f"{r['max_s']:>8.2f} {gpu:>5}  {', '.join(r['unstable']) or '-'}")


if __name__ == "__main__":
    main()
