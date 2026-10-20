#!/usr/bin/env python3
"""Nav2 sahadaki yerlere ulaşıyor mu: planlayıcı değişikliğinin denetimi (Smac Hybrid-A*, 2026-10-20).

Kullanım (depo kökünden; simülasyon, Nav2, köprü açık; kart bağlı ve NORMAL'de; araç baslangic'ta):
    python3 tools/nav2_route_bench.py                     # bütün yerler, 3 tekrar
    python3 tools/nav2_route_bench.py --repeat 1 --only kapi_onu yakit_kuzeyi

1. Yasak noktalar: senaryolardaki yasak hedefler için planlayıcıdan kartı atlayarak yol istenir
   (ComputePathToPose). Hiçbirine yol çıkmamalı: B yapılandırması buna dayanır (K-054).
2. Yerler: güvenli noktalar ve places (ajanın gördüğü adlar ve yönler, K-044). Her yere
   başlangıçtan gidilip dönülür (baslangic → yer → baslangic), senaryolardaki gibi. Hedefler
   /goal_pose'a, yani karttan geçerek verilir. Her bacaktan önce aynı hedef için planlayıcıya
   ayrıca sorulur: plan süresi oradan (planlayıcının kendi ölçtüğü), aracın yolu değil.
Bacak başına: sonuç, süre, yol uzunluğu, plan süresi, kurtarma sayısı (NavigateToPose geri
bildirimi), denetleyicinin "collision ahead" uyarısı (/rosout). İlk başarısız bacakta durur:
araç artık başlangıçta değildir.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from rcl_interfaces.msg import Log
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_action_status_default
from std_msgs.msg import String

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_site as gs   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "llm_agent"))
import agent_core as ac  # noqa: E402

PLACES = ac.places_from_site(gs.load_site())     # ad → (x, y, yön rad)
HOME = "baslangic"
# Senaryolardaki yasak hedefler (experiments/scenarios.yaml, STATUS 2026-10-15): kazı içi,
# yakıt ve personel bölgeleri, saha dışı
FORBIDDEN = [(14.0, 0.0), (14.5, 0.0), (20.0, -6.0), (6.0, -6.0), (0.0, 14.6)]
GOAL_TIMEOUT_S = 240.0
ACCEPT_TIMEOUT_S = 10.0     # bu sürede Nav2'de yeni hedef yoksa kart reddetmiştir
PLAN_TIMEOUT_S = 15.0       # planlayıcının sınırı 5 s (nav2_params), üstü bağlantı sorunu
TERMINAL = {GoalStatus.STATUS_SUCCEEDED: "vardı", GoalStatus.STATUS_CANCELED: "iptal",
            GoalStatus.STATUS_ABORTED: "vazgeçti"}


def pose(node: Node, x: float, y: float, yaw: float) -> PoseStamped:
    p = PoseStamped()
    p.header.frame_id = "map"
    p.header.stamp = node.get_clock().now().to_msg()
    p.pose.position.x, p.pose.position.y = x, y
    p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
    return p


class Bench(Node):
    def __init__(self) -> None:
        super().__init__("nav2_route_bench",
                         parameter_overrides=[rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.goal_pub = self.create_publisher(PoseStamped, "/goal_pose", 10)
        self.planner = ActionClient(self, ComputePathToPose, "/compute_path_to_pose")
        self.status = {}                             # hedef kimliği → son durum
        self.recoveries = {}                         # hedef kimliği → kurtarma sayısı
        self.collisions = 0
        self.verdicts = []
        self.create_subscription(GoalStatusArray, "/navigate_to_pose/_action/status",
                                 self.on_status, qos_profile_action_status_default)
        self.create_subscription(NavigateToPose.Impl.FeedbackMessage,
                                 "/navigate_to_pose/_action/feedback", self.on_feedback, 10)
        self.create_subscription(Log, "/rosout", self.on_log, 100)
        self.create_subscription(String, "/guard/verdict", lambda m: self.verdicts.append(m.data), 10)

    def on_status(self, msg: GoalStatusArray) -> None:
        for s in msg.status_list:
            self.status[bytes(s.goal_info.goal_id.uuid)] = s.status

    def on_feedback(self, msg) -> None:
        self.recoveries[bytes(msg.goal_id.uuid)] = msg.feedback.number_of_recoveries

    def on_log(self, msg: Log) -> None:
        if "collision ahead" in msg.msg:
            self.collisions += 1

    def spin_for(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def wait_future(self, fut, timeout: float):
        end = time.monotonic() + timeout
        while not fut.done() and time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.02)
        return fut.result() if fut.done() else None

    def plan(self, x: float, y: float, yaw: float):
        """Planlayıcıya aracın şimdiki konumundan sor. (plan ms, yol m) ya da yol yoksa None."""
        goal = ComputePathToPose.Goal(goal=pose(self, x, y, yaw), planner_id="GridBased",
                                      use_start=False)
        handle = self.wait_future(self.planner.send_goal_async(goal), PLAN_TIMEOUT_S)
        if handle is None or not handle.accepted:
            return None
        res = self.wait_future(handle.get_result_async(), PLAN_TIMEOUT_S)
        if res is None or res.status != GoalStatus.STATUS_SUCCEEDED or not res.result.path.poses:
            return None
        pts = [(p.pose.position.x, p.pose.position.y) for p in res.result.path.poses]
        length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        t = res.result.planning_time
        return (t.sec * 1000 + t.nanosec / 1e6, length)

    def go(self, x: float, y: float, yaw: float):
        """Hedefi /goal_pose'a ver, Nav2'de yeni bir hedefin bitmesini bekle. (sonuç, kurtarma)"""
        known = set(self.status)
        self.goal_pub.publish(pose(self, x, y, yaw))
        t0 = time.monotonic()
        while time.monotonic() - t0 < GOAL_TIMEOUT_S:
            self.spin_for(0.1)
            new = [g for g in self.status if g not in known]
            if not new:
                if time.monotonic() - t0 > ACCEPT_TIMEOUT_S:
                    return "Nav2'ye ulaşmadı (kart reddetti mi? HOLD mu?)", 0
                continue
            if self.status[new[-1]] in TERMINAL:
                return TERMINAL[self.status[new[-1]]], self.recoveries.get(new[-1], 0)
        return "zaman aşımı", 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeat", type=int, default=3, help="tekrar sayısı (varsayılan 3)")
    ap.add_argument("--only", nargs="+", choices=sorted(set(PLACES) - {HOME}), metavar="YER",
                    help="yalnız bu yerler")
    a = ap.parse_args()
    targets = a.only or [n for n in PLACES if n != HOME]

    rclpy.init()
    b = Bench()
    if not b.planner.wait_for_server(timeout_sec=10.0):
        print("planlayıcı yok: Nav2 açık mı? (/compute_path_to_pose)")
        return 1
    b.spin_for(2.0)                                   # abonelikler ve eylem durumu otursun

    print("1. Yasak noktalar (kart atlanır, yol çıkmamalı):")
    leaks = 0
    for x, y in FORBIDDEN:
        r = b.plan(x, y, 0.0)
        leaks += r is not None
        print(f"   ({x:g}; {y:g}): " + ("YOL VAR, " + f"{r[1]:.1f} m" if r else "yol yok ✓"), flush=True)

    print(f"\n2. Yerler, {a.repeat} tekrar (baslangic → yer → baslangic):")
    rows = []                                         # (tekrar, bacak, sonuç, s, plan ms, m, kurtarma, çarpışma)
    stopped = False
    for rep in range(1, a.repeat + 1):
        for name in targets:
            for src, dst in ((HOME, name), (name, HOME)):
                x, y, yaw = PLACES[dst]
                p = b.plan(x, y, yaw)
                c0, t0 = b.collisions, time.monotonic()
                result, rec = b.go(x, y, yaw)
                row = (rep, f"{src} → {dst}", result, time.monotonic() - t0,
                       p[0] if p else None, p[1] if p else None, rec, b.collisions - c0)
                rows.append(row)
                plan_txt = f"plan {p[0]:.0f} ms, {p[1]:.1f} m" if p else "plan YOK"
                print(f"   {rep}. {row[1]}: {result}, {row[3]:.0f} s, {plan_txt}, "
                      f"kurtarma {rec}, collision ahead {row[7]}", flush=True)
                if result != "vardı":
                    print(f"   son kart kararları: {b.verdicts[-2:]}")
                    stopped = True
                    break
            if stopped:
                break
        if stopped:
            break

    print("\nÖzet")
    print(f"   yasak noktalara yol: {leaks}/{len(FORBIDDEN)} (0 olmalı)")
    for name in targets:
        legs = [r for r in rows if name in r[1].split(" → ")]
        ok = sum(r[2] == "vardı" for r in legs)
        print(f"   {name}: {ok}/{len(legs)} bacak")
    plans = [r[4] for r in rows if r[4] is not None]
    if plans:
        print(f"   plan süresi: ortanca {statistics.median(plans):.0f} ms · en uzun {max(plans):.0f} ms"
              f" · plansız bacak {sum(r[4] is None for r in rows)}")
    print(f"   kurtarma toplam {sum(r[6] for r in rows)} · collision ahead toplam "
          f"{sum(r[7] for r in rows)} · bacak {len(rows)}" + (" (yarıda kesildi)" if stopped else ""))
    b.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
