#!/usr/bin/env python3
"""Çelişki testi (Faz 5 öncesi): model yer + koordinat birlikte verince ne oluyor.

Kullanım (Ollama servisi açık):
    python3 tools/agent_conflict_bench.py                       # sıcaklık 0,7, seed 1…10 (K-053)
    python3 tools/agent_conflict_bench.py --seeds 20 -v         # hatalı koşuların adımlarını yaz

2026-10-15'te simde iki görevde model önce {yer, uydurma x/y} verdi; K-052'nin "ikisini birden
verdin" mesajından sonra yer adını bırakıp uydurma koordinatı tuttu. llm_select_bench yalnız
ilk çağrıya baktığı için bunu göremez. Bu test ajanın gerçek döngüsünü (agent_core.Agent: istem,
araçlar, çelişki kuralı) gerçek modelle çalıştırır; dünya yerine sahte yürütücü kullanır:
- git: hedef kartın Python eşiyle (gen_site.geofence_cm) denetlenir; geçerse araç hedefe
  ışınlanır, reddedilirse köprünün gerçek metni (convert.feedback_text, D) döner.
- hiz_siniri: LIMIT (0 < v ≤ 0,6 m/s). bekle, dur: kabul.
Konum hatası, CONSISTENCY ve Nav2'nin ulaşamaması üretilmez: yalnız modelin karar zinciri ölçülür.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_site as gs   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "llm_agent"))
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "guard_bridge"))
import agent_core as ac  # noqa: E402
import convert as cv  # noqa: E402

SITE = gs.load_site()
PLACES = ac.places_from_site(SITE)
V_MAX_MMS = 600                       # RULES §1: bekçinin hız sınırı

# (kullanıcı cümlesi, beklenen yer, başlangıç konumu)
CASES = [
    ("Kapı önüne git.", "kapi_onu", (0, 0)),
    ("Kapıya git.", "kapi_onu", (0, 0)),
    ("Konteynerin arkasına git.", "konteyner_arkasi", (0, 0)),
    ("Konteynerin önüne git.", "konteyner_onu", (0, 0)),
    ("Başlangıç noktasına dön.", "baslangic", (8.5, 1)),
    ("Geldiğin yere geri dön.", "baslangic", (8.5, 1)),
    ("Sahanın kuzeybatısındaki noktaya git.", "kuzeybati", (0, 0)),
    ("Kazının doğusuna git", "kazi_dogu", (0, 0)),             # 2026-10-15, simde
    ("Yakıt deposunun kuzeyine git", "yakit_kuzeyi", (0, 0)),  # 2026-10-15, simde
    ("Kazı alanının batısına git.", "kazi_bati", (0, 0)),
    ("Kazı alanının kuzeyine git.", "kazi_kuzeyi", (0, 0)),
    ("Konteyner arkasına git, orada 20 saniye bekle.", "konteyner_arkasi", (0, 0)),
]


def _pt(x, y):
    return f"({x:.2f}; {y:.2f})".replace(".", ",")


class FakeWorld:
    """agent_core.Executor: kartın kararı Python eşleriyle, varış anında."""

    def __init__(self, start):
        self.x, self.y = start

    def observe(self):
        return ac.Observation(self.x, self.y, time.monotonic())

    def execute(self, task):
        cmd = task["cmd"]
        if cmd == "git":
            p = (round(task["x"] * 100), round(task["y"] * 100))
            verdict = gs.geofence_cm(SITE["allowed"], list(SITE["forbidden"].values()), p)
            if verdict != gs.OK:
                reason = "GOAL_IN_FORBIDDEN" if verdict == gs.IN_FORBIDDEN else "GOAL_OUTSIDE_ALLOWED"
                hx, hy = gs.nearest_safe(list(SITE["safe"].values()), SITE["home"], p)
                return False, cv.feedback_text("REJECTED", "GEOFENCE", reason, 0, 0, 0, hx, hy,
                                               full=True, safe_points=SITE["safe"])
            self.x, self.y = task["x"], task["y"]
            target = _pt(task["x"], task["y"])
            if task.get("yer"):
                target = f"{task['yer']} {target}"
            return True, f"Komut kabul edildi. Hedefe varıldı: {target}."
        if cmd == "hiz_siniri":
            v = round(task["deger_mps"] * 1000)
            if not 0 < v <= V_MAX_MMS:
                reason = "ABOVE_MAX" if v > 0 else "NOT_POSITIVE"
                return False, cv.feedback_text("REJECTED", "LIMIT", reason, v, 1, V_MAX_MMS, 0, 0,
                                               full=True)
            return True, f"Komut kabul edildi. Hız sınırı {task['deger_mps']:g} m/s yapıldı."
        if cmd == "bekle":
            return True, f"Komut kabul edildi. {task['sure_s']:g} saniye beklendi."
        return True, "Komut kabul edildi. Araç durduruldu."


def _is_conflict(step):
    return step["task"] is None and "ikisini birden" in step["result"]


def _choice(step):
    """Çelişkiden sonraki adım: modelin seçtiği."""
    if step is None:
        return "araç çağırmadı"
    if _is_conflict(step):
        return "yine ikisi"
    a = step["args"]
    if step["tool"] != "git":
        return f"başka araç ({step['tool']})"
    return "yer" if a.get("yer") else "x/y"


def run_case(chat_for_seed, text, want, start, seed):
    world = FakeWorld(start)
    steps = []
    agent = ac.Agent(chat_for_seed(seed), world, PLACES,
                     log=lambda e: steps.append(e) if e["event"] == "adım" else None)
    out = agent.run(text)
    wx, wy, _ = PLACES[want]
    first_conflict = next((i for i, s in enumerate(steps) if _is_conflict(s)), None)
    after = None
    if first_conflict is not None:
        after = _choice(steps[first_conflict + 1] if first_conflict + 1 < len(steps) else None)
    arrived = abs(world.x - wx) < 0.01 and abs(world.y - wy) < 0.01
    return {"conflict": first_conflict is not None, "after": after, "arrived": arrived,
            "steps": steps, "status": out["status"], "summary": out["summary"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default=ac.MODEL)
    ap.add_argument("--temperature", type=float, default=0.7)   # K-053
    ap.add_argument("--seeds", type=int, default=10, help="seed 1, 2, … (K-053: tekrar numarası)")
    ap.add_argument("-v", "--verbose", action="store_true", help="hatalı koşuların adımlarını yaz")
    args = ap.parse_args()

    def chat_for_seed(seed):
        return ac.ollama_chat(args.model, dict(ac.OPTIONS, temperature=args.temperature, seed=seed))

    print(f"{args.model}, sıcaklık {args.temperature:g}, seed 1…{args.seeds}\n")
    print(f"{'cümle':48} {'çelişki':>8} {'sonra yer':>10} {'sonra x/y':>10} {'diğer':>6} {'doğru yer':>10}")
    total = Counter()
    for text, want, start in CASES:
        c = Counter()
        for seed in range(1, args.seeds + 1):
            r = run_case(chat_for_seed, text, want, start, seed)
            c["n"] += 1
            c["conflict"] += r["conflict"]
            c["arrived"] += r["arrived"]
            if r["after"] == "yer":
                c["yer"] += 1
            elif r["after"] == "x/y":
                c["xy"] += 1
            elif r["after"] is not None:
                c["other"] += 1
            if args.verbose and (r["conflict"] or not r["arrived"]):
                print(f"  seed {seed}: {text!r} → {r['status']}, vardı={r['arrived']}")
                for s in r["steps"]:
                    print(f"    {s['tool']} {s['args']} → {s['result'][:90]}")
                print(f"    özet: {r['summary'][:120]}")
        total.update(c)
        print(f"{text[:48]:48} {c['conflict']:>4}/{c['n']:<3} {c['yer']:>10} {c['xy']:>10} "
              f"{c['other']:>6} {c['arrived']:>6}/{c['n']:<3}")
    print(f"\n{'TOPLAM':48} {total['conflict']:>4}/{total['n']:<3} {total['yer']:>10} {total['xy']:>10} "
          f"{total['other']:>6} {total['arrived']:>6}/{total['n']:<3}")


if __name__ == "__main__":
    main()
