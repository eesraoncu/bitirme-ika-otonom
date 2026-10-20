#!/usr/bin/env python3
"""Faz 5 koşu çalıştırıcı: senaryo × yapılandırma × seed (K-055, K-064).

Kullanım (depo kökünden; kart bağlı ve E5V'de (K-061), Ollama çalışıyor, başka simülasyon kapalı):
    python3 ros2_ws/src/experiments/run.py --scenario normal_1 --config D --seeds 1
    python3 ros2_ws/src/experiments/run.py --scenario normal_1 normal_2 --config A B C D --seeds 1-3
    python3 ros2_ws/src/experiments/run.py --scenario normal_1 --config D --seeds 1 --gui    # pencereli

Her koşu (K-065): düzeni baştan aç (experiment.launch.py; simülasyon dahil, araç başlangıçta) →
hazır olmasını bekle → modeli ısıt → SIFIRLA → kaydı başlat (rosbag) → görevi ver (/agent/task) → ajan bitirene
ya da süre dolana kadar bekle → aracın durmasını bekle → kaydı kapat → değerlendir (evaluate.py),
results.csv'ye ekle → düzeni kapat. Süreler simülasyon saatiyle.

Altyapı senaryolarında (scenarios.yaml goal) LLM atlanır: görev /agent/task yerine doğrudan
/guard/task'a, git(goal), C/D'de karttan geçerek. İnanç başlangıç noktası (araç her koşuda orada).
Altyapı olayları (scenarios.yaml event): araç after_motion_s hareket ettikten sonra
- sigstop: köprü süreci dondurulur (C/D agent_bridge, A/B direct_bridge; K-058), sonda çözülür.
- unplug: ekrana "KABLOYU ÇEK" yazılır; kopma agent_bridge'in günlüğünden yakalanır (K-029).
  Koşudan sonra kablo geri takılınca kart yeniden başlar (K-061), sonraki koşu bunu bekler.
Olaylı koşu araç durunca (ya da süre dolunca) biter.

Modeli ısıtma: Ollama modeli GPU'ya soğuk yüklerken bilgisayar ~0,5 s takılıyor, iki kanalın
çerçeveleri birlikte gecikiyor ve kart kalp atışını kaçırıp HOLD'a düşüyor (2026-10-20: üç soğuk
yüklemenin ikisinde). Model SIFIRLA'dan önce yüklenir ve yüklü kalır (keep_alive -1).

Koşu klasörü (--out, depo dışında): meta.json, bag/, launch.log.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import urllib.request
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import rclpy
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import Log
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String
from std_srvs.srv import Trigger
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "shared" / "protocol" / "python"))
import evaluate as ev  # noqa: E402
ac = ev.ac
from ika_protocol.link import AGENT_PORT  # noqa: E402

LAUNCH = HERE / "launch" / "experiment.launch.py"
TOPICS = ["/agent/task", "/agent/log", "/guard/task", "/guard/feedback", "/guard/verdict",
          "/guard/status", "/cmd_vel", "/cmd_vel_nav", "/amcl_pose", "/sim/odom", "/sim/stats",
          "/sim/contact", "/rosout"]
READY_TIMEOUT_S = 120.0      # gerçek saat: düzenin açılması
RESET_TRIES = 10
MOVING_MPS = 0.05
STOPPED_HOLD_S = 3.0         # olaylı koşu: araç bu kadar durunca biter
SETTLE_S = 3.0               # bitişten sonra kayda devam (aracın son hareketi)
STACK = r"ign gazebo|nav2_|_bridge.py|parameter_bridge|lifecycle_manager|agent_node.py|static_transform"


def launch_constant(name: str):
    """experiment.launch.py'deki sabit (sıcaklık tek yerde, K-053)."""
    spec = importlib.util.spec_from_file_location("experiment_launch", LAUNCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, name)


def seeds(text: str) -> List[int]:
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def alive() -> List[str]:
    r = subprocess.run(["pgrep", "-af", STACK], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if "pgrep" not in l and "run.py" not in l]


class Runner(Node):
    def __init__(self) -> None:
        super().__init__("experiment_runner")
        self.sim_now = 0.0
        self.speed = 0.0
        self.events: List[dict] = []
        self.unplugged_at: Optional[float] = None
        self.create_subscription(Clock, "/clock", self.on_clock, 10)
        self.create_subscription(Odometry, "/sim/odom", self.on_odom, 10)
        self.create_subscription(String, "/agent/log", lambda m: self.events.append(json.loads(m.data)), 50)
        self.create_subscription(Log, "/rosout", self.on_rosout, 100)
        self.task_pub = self.create_publisher(String, "/agent/task", 10)
        self.guard_task_pub = self.create_publisher(String, "/guard/task", 10)
        self.reset = self.create_client(Trigger, "/guard/reset")
        self.active = {n: self.create_client(Trigger, f"/{n}/is_active")
                       for n in ("lifecycle_manager_localization", "lifecycle_manager_navigation")}

    def on_clock(self, m: Clock) -> None:
        self.sim_now = m.clock.sec + m.clock.nanosec / 1e9

    def on_odom(self, m: Odometry) -> None:
        v = m.twist.twist.linear
        self.speed = (v.x ** 2 + v.y ** 2) ** 0.5

    def on_rosout(self, m: Log) -> None:
        if self.unplugged_at is None and m.name == "agent_bridge" and "ajan kanalı koptu" in m.msg:
            self.unplugged_at = self.sim_now

    def spin_for(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def call(self, client, timeout: float = 3.0) -> Optional[Trigger.Response]:
        if not client.service_is_ready():
            return None
        fut = client.call_async(Trigger.Request())
        end = time.monotonic() + timeout
        while not fut.done() and time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.02)
        return fut.result() if fut.done() else None

    def ready(self) -> bool:
        if any(not (r := self.call(c)) or not r.success for c in self.active.values()):
            return False
        return self.reset.service_is_ready() and self.count_subscribers("/agent/task") > 0

    def wait_ready(self) -> bool:
        end = time.monotonic() + READY_TIMEOUT_S
        while time.monotonic() < end:
            if self.ready():
                return True
            self.spin_for(1.0)
        return False

    def do_reset(self) -> Optional[str]:
        for _ in range(RESET_TRIES):
            r = self.call(self.reset)
            if r is not None and r.success:
                return r.message
            self.spin_for(2.0)
        return None


def direct_task(place: str, sim_now: float) -> Dict:
    """LLM'siz görev: git(place), inanç başlangıç noktası (/guard/task biçimi, K-050)."""
    site = ev.gs.load_site()
    x, y, yaw = ac.places_from_site(site)[place]
    hx, hy = site["home"]
    return {"id": "dogrudan", "cmd": "git", "x": x, "y": y, "yaw": yaw, "yer": place,
            "belief": {"x": hx / 100, "y": hy / 100, "stamp": sim_now}}


def warm_model() -> None:
    """Modeli GPU'ya yükle ve yüklü tut (yukarıda: soğuk yükleme kartı HOLD'a düşürüyor)."""
    body = json.dumps({"model": ac.MODEL, "messages": [{"role": "user", "content": "hazır"}],
                       "stream": False, "keep_alive": -1, "options": {"num_predict": 1}}).encode()
    req = urllib.request.Request(f"{ac.OLLAMA_URL}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=120).read()


def bridge_pid(session: int, config: str) -> Optional[int]:
    script = "agent_bridge.py" if launch_constant("CONFIGS")[config]["guard"] else "direct_bridge.py"
    r = subprocess.run(["pgrep", "-s", str(session), "-f", script], capture_output=True, text=True)
    pids = [int(p) for p in r.stdout.split()]
    return pids[0] if pids else None


def stop_stack(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        subprocess.run(["pkill", "-TERM" if sig == signal.SIGTERM else "-KILL", "-f", r"ign gazebo (server|gui)"])
        end = time.monotonic() + 30
        while alive() and time.monotonic() < end:
            time.sleep(1)
        if not alive():
            return
    print("  UYARI: kapanmayan süreçler:", *alive(), sep="\n    ")


def run_one(node: Runner, spec: Dict, config: str, seed: int, gui: bool, out: Path,
            results: Path, temperature: float) -> Optional[Dict]:
    name = f"{dt.datetime.now():%Y%m%d-%H%M%S}_{spec['id']}_{config}_{seed}"
    run_dir = out / name
    run_dir.mkdir(parents=True)
    meta = {"name": name, "date": f"{dt.date.today()}", "scenario": spec["id"], "config": config,
            "seed": seed, "temperature": temperature, "event_t": None, "timed_out": False}
    print(f"\n=== {name}", flush=True)
    with (run_dir / "launch.log").open("w") as log:
        proc = subprocess.Popen(["ros2", "launch", str(LAUNCH), f"config:={config}", f"seed:={seed}",
                                 f"gui:={'true' if gui else 'false'}"],
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    bag = None
    frozen = None
    try:
        if not node.wait_ready():
            print("  HATA: düzen hazır olmadı (launch.log)")
            return None
        warm_model()
        node.spin_for(2.0)                         # ısıtmanın takılması geçsin, sonra SIFIRLA
        meta["reset"] = node.do_reset()
        if meta["reset"] is None:
            print("  HATA: SIFIRLA kabul edilmedi (kart bağlı mı, HOLD'da mı?)")
            return None
        bag = subprocess.Popen(["ros2", "bag", "record", "-o", str(run_dir / "bag"), *TOPICS],
                               stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True)
        node.spin_for(3.0)                         # kaydın abonelikleri otursun
        node.events.clear()
        node.unplugged_at = None
        t0 = meta["task_t"] = node.sim_now
        if spec.get("goal"):
            meta["direct"] = True
            node.guard_task_pub.publish(String(data=json.dumps(direct_task(spec["goal"], t0))))
        else:
            node.task_pub.publish(String(data=spec["text"]))
        event = spec.get("event")
        motion_t = stopped_t = None
        while True:
            node.spin_for(0.1)
            now = node.sim_now
            if now - t0 > spec["timeout_s"]:
                meta["timed_out"] = True
                break
            if node.speed >= MOVING_MPS and motion_t is None:
                motion_t = now
            if event and meta["event_t"] is None and motion_t is not None \
                    and now - motion_t >= event["after_motion_s"]:
                if event["type"] == "sigstop":
                    frozen = bridge_pid(proc.pid, config)
                    if frozen is not None:
                        os.kill(frozen, signal.SIGSTOP)
                        meta["event_t"] = now
                        print(f"  olay: köprü donduruldu (pid {frozen}) t={now:.1f}", flush=True)
                elif event["type"] == "unplug" and not meta.get("prompted"):
                    meta["prompted"] = now
                    print("\a\n  >>> KABLOYU ŞİMDİ ÇEK (CN1, ajan kablosu) <<<\n", flush=True)
            if event and event["type"] == "unplug" and node.unplugged_at is not None and meta["event_t"] is None:
                meta["event_t"] = node.unplugged_at
                print(f"  olay: kablo çekildi t={meta['event_t']:.1f}", flush=True)
            if event and meta["event_t"] is not None:     # olaylı koşu: araç durunca biter
                stopped_t = (stopped_t or now) if node.speed < ev.STOP_MPS else None
                if stopped_t is not None and now - stopped_t >= STOPPED_HOLD_S:
                    break
            elif not event and any(e.get("event") in ("sonuç", "hata") for e in node.events):
                break
        meta["end_t"] = node.sim_now
        node.spin_for(SETTLE_S)
    finally:
        if bag is not None:
            os.killpg(bag.pid, signal.SIGINT)
            bag.wait(timeout=20)
        if frozen is not None:
            os.kill(frozen, signal.SIGCONT)
        stop_stack(proc)
        (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    if spec.get("event", {}).get("type") == "unplug":
        input("  Kabloyu geri tak (kart yeniden başlar), sonra Enter: ")
        while not Path(AGENT_PORT).exists():
            time.sleep(1)
    row = ev.make_row(meta, spec, ev.read_bag(run_dir / "bag"))
    ev.append_row(row, results)
    print(f"  başarı {row['basari']} · ajan {row['ajan_sonu']} · adım {row['adim']} · ret {row['ret']} "
          f"· güvensiz komut {row['guvensiz_komut']}/{row['guvensiz_komut_gecen']} geçen · "
          f"güvensiz sonuç {row['guvensiz_sonuc']} · süre {row['sure_s']} s · sim {row['sim_hiz_orani']}",
          flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", nargs="+", required=True, help="scenarios.yaml'daki id'ler")
    ap.add_argument("--config", nargs="+", default=list("ABCD"), choices=list("ABCD"))
    ap.add_argument("--seeds", default="1", help="ör. 1, 1-3, 1,4 (seed = tekrar numarası, K-053)")
    ap.add_argument("--gui", action="store_true", help="Gazebo penceresi açık")
    ap.add_argument("--out", type=Path, default=Path.home() / "ika_kosular", help="koşu klasörleri")
    ap.add_argument("--results", type=Path, default=ev.RESULTS)
    a = ap.parse_args()
    if alive():
        print("Önce açık simülasyonu ve köprüleri kapat:", *alive(), sep="\n  ")
        return 1
    specs = [ev.scenario(s) for s in a.scenario]
    temperature = launch_constant("TEMPERATURE")
    rclpy.init()
    node = Runner()
    try:
        for spec in specs:
            for config in [c for c in a.config if c in spec.get("configs", list("ABCD"))]:
                for seed in seeds(a.seeds):
                    run_one(node, spec, config, seed, a.gui, a.out.expanduser(), a.results, temperature)
    except KeyboardInterrupt:
        print("\nyarıda kesildi")
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
