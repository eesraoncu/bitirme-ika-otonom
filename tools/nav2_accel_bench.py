#!/usr/bin/env python3
"""Nav2'nin hız komutlarında en büyük adım: bekçinin doğrusal ivme sınırı için (RULES §1, K-039).

Kullanım (depo kökünden; simülasyon, Nav2, köprü açık; kart bağlı ve NORMAL'de):
    python3 tools/nav2_accel_bench.py
    python3 tools/nav2_accel_bench.py --csv /tmp/nav2_cmd.csv    # ham kayıt da yazılsın

Araç (0, 0)'dan başlayıp TOUR'daki noktaları sırayla dolaşır: hedefler /goal_pose'a, yani
karttan geçerek verilir (K-040); her hedefte Nav2'nin NavigateToPose eyleminin bitmesi beklenir.
Bu sırada iki konu kaydedilir:
- /cmd_vel_raw: denetleyicinin ve kurtarma hareketlerinin ham çıktısı
- /cmd_vel_smoothed: velocity_smoother'dan sonra (K-046)
- /cmd_vel_nav: collision_monitor'dan sonra, kartın VELOCITY_CMD olarak gördüğü hız
Bekçi ivmeyi komut başına hız farkıyla denetler (RULES §3.2: Δv_max = a_max × 50 ms);
bu yüzden asıl ölçü ardışık iki komut arasındaki |Δv| ve |Δω|. Aralıklar duvar
saatiyle (simülasyon gerçek zamana yakın; oran sonda yazılır).
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from geometry_msgs.msg import PoseStamped, Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_action_status_default
from std_msgs.msg import String

# Yalnız bu ölçümün rotası, sahanın parçası değil (saha: shared/site/ika_saha.yaml). Her nokta
# 2026-10-14'te iz hesabıyla denetlendi: yerinde dönen izin (pay dahil yarıçap 1,56 m) 0,3 m
# yakınında harita engeli de keepout maskesi de yok, yani varış yönü önemsiz. Güvenli noktalar
# kullanılmadı: konteyner_arkasi sınıra 12 cm, konteyner_onu konteynere değiyor (STATUS).
TOUR = [("guney", 13.0, -5.5), ("dogu", 24.0, -0.5), ("orta", 10.0, 0.0), ("bati", 2.0, 0.5)]
START = (0.0, 0.0)
TOPICS = ["/cmd_vel_raw", "/cmd_vel_smoothed", "/cmd_vel_nav"]
T_NOMINAL_S = 0.05          # RULES §3.2: Nav2 20 Hz
GOAL_TIMEOUT_S = 240.0
ACCEPT_TIMEOUT_S = 10.0     # bu sürede Nav2'de yeni hedef yoksa kart reddetmiştir
MOVING_MPS = 0.05           # bunun altı "yerinde" sayılır (ω'yu yol takibinden ayırmak için)
TERMINAL = {GoalStatus.STATUS_SUCCEEDED: "vardı", GoalStatus.STATUS_CANCELED: "iptal",
            GoalStatus.STATUS_ABORTED: "vazgeçti"}


class Bench(Node):
    def __init__(self) -> None:
        super().__init__("nav2_accel_bench",
                         parameter_overrides=[rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.goal_pub = self.create_publisher(PoseStamped, "/goal_pose", 10)
        self.samples = {t: [] for t in TOPICS}      # konu → [(duvar s, v, ω, hedef no)]
        self.leg = 0
        self.status = {}                             # hedef kimliği → son durum
        self.verdicts = []
        for t in TOPICS:
            self.create_subscription(Twist, t, lambda m, t=t: self.on_cmd(t, m), 50)
        self.create_subscription(GoalStatusArray, "/navigate_to_pose/_action/status",
                                 self.on_status, qos_profile_action_status_default)
        self.create_subscription(String, "/guard/verdict", lambda m: self.verdicts.append(m.data), 10)

    def on_cmd(self, topic, msg: Twist) -> None:
        self.samples[topic].append((time.monotonic(), msg.linear.x, msg.angular.z, self.leg))

    def on_status(self, msg: GoalStatusArray) -> None:
        for s in msg.status_list:
            self.status[bytes(s.goal_info.goal_id.uuid)] = s.status

    def spin_for(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def go(self, x: float, y: float, yaw: float) -> str:
        """Hedefi /goal_pose'a ver, Nav2'de yeni bir hedefin bitmesini bekle."""
        known = set(self.status)
        p = PoseStamped()
        p.header.frame_id = "map"
        p.header.stamp = self.get_clock().now().to_msg()
        p.pose.position.x, p.pose.position.y = x, y
        p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self.goal_pub.publish(p)
        t0 = time.monotonic()
        while time.monotonic() - t0 < GOAL_TIMEOUT_S:
            self.spin_for(0.1)
            new = [s for g, s in self.status.items() if g not in known]
            if not new:
                if time.monotonic() - t0 > ACCEPT_TIMEOUT_S:
                    return "Nav2'ye ulaşmadı (kart reddetti mi? HOLD mu?)"
                continue
            if new[-1] in TERMINAL:
                return TERMINAL[new[-1]]
        return "zaman aşımı"


def _pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def report(topic, rows) -> None:
    if len(rows) < 2:
        print(f"\n{topic}: {len(rows)} mesaj, ölçüm yok")
        return
    gaps = [b[0] - a[0] for a, b in zip(rows, rows[1:])]
    steps = [(abs(b[1] - a[1]), abs(b[2] - a[2]), i + 1, g) for i, (a, b, g)
             in enumerate(zip(rows, rows[1:], gaps))]
    # 0,5 s'den uzun boşluk yeni bir hareketin başıdır (hedefler arası); adımı yine sayılır,
    # çünkü kart son gönderdiğiyle kıyaslar, aradaki sessizlikle değil.
    dv = [s[0] for s in steps]
    dw = [s[1] for s in steps]
    moving_w = [abs(r[2]) for r in rows if abs(r[1]) >= MOVING_MPS]
    inplace_w = [abs(r[2]) for r in rows if abs(r[1]) < MOVING_MPS]
    short = [g for g in gaps if g < 0.5]

    print(f"\n{topic}: {len(rows)} mesaj")
    print(f"  aralık (0,5 s altı): ortanca {statistics.median(short) * 1000:.0f} ms · "
          f"%95 {_pct(short, 0.95) * 1000:.0f} ms · en uzun {max(short) * 1000:.0f} ms"
          f" · 0,5 s üstü boşluk {len(gaps) - len(short)}")
    print(f"  |v| en çok {max(abs(r[1]) for r in rows):.3f} m/s · |ω| en çok "
          f"{max(abs(r[2]) for r in rows):.3f} rad/s (yol takibinde "
          f"{max(moving_w, default=0):.3f}, yerinde {max(inplace_w, default=0):.3f})")
    print(f"  |Δv| komut başına: en çok {max(dv):.3f} · %99 {_pct(dv, 0.99):.3f} · "
          f"%95 {_pct(dv, 0.95):.3f} m/s  (÷ {T_NOMINAL_S * 1000:.0f} ms → en çok "
          f"{max(dv) / T_NOMINAL_S:.2f} m/s²)")
    print(f"  |Δω| komut başına: en çok {max(dw):.3f} · %99 {_pct(dw, 0.99):.3f} · "
          f"%95 {_pct(dw, 0.95):.3f} rad/s (÷ {T_NOMINAL_S * 1000:.0f} ms → en çok "
          f"{max(dw) / T_NOMINAL_S:.2f} rad/s²)")
    for name, k in (("Δv", 0), ("Δω", 1)):
        print(f"  en büyük 5 {name} (önceki → sonraki v, ω · aralık · hedef):")
        for s in sorted(steps, key=lambda s: -s[k])[:5]:
            a, b = rows[s[2] - 1], rows[s[2]]
            print(f"    {s[k]:.3f}: v {a[1]:+.3f} → {b[1]:+.3f}, ω {a[2]:+.3f} → {b[2]:+.3f} · "
                  f"{s[3] * 1000:.0f} ms · {TOUR[b[3]][0]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, help="ham kaydı bu dosyaya yaz")
    a = ap.parse_args()

    rclpy.init()
    b = Bench()
    b.spin_for(2.0)                                   # abonelikler ve eylem durumu otursun
    sim0, wall0 = b.get_clock().now().nanoseconds, time.monotonic()

    prev = START
    for i, (name, x, y) in enumerate(TOUR):
        b.leg = i
        yaw = math.atan2(y - prev[1], x - prev[0])   # varış yönü: geldiği doğrultu
        t0 = time.monotonic()
        result = b.go(x, y, yaw)
        print(f"{i + 1}/{len(TOUR)} {name} ({x:g}, {y:g}): {result}, "
              f"{time.monotonic() - t0:.0f} s", flush=True)
        if result not in ("vardı",):
            print(f"  son kart kararları: {b.verdicts[-2:]}")
            break
        prev = (x, y)
    b.spin_for(1.0)

    rtf = (b.get_clock().now().nanoseconds - sim0) / 1e9 / (time.monotonic() - wall0)
    print(f"\nsimülasyon / gerçek zaman: {rtf:.2f}")
    for t in TOPICS:
        report(t, b.samples[t])

    if a.csv:
        with a.csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["konu", "duvar_s", "v_mps", "w_radps", "hedef"])
            for t in TOPICS:
                w.writerows([t, f"{r[0]:.4f}", r[1], r[2], TOUR[r[3]][0]] for r in b.samples[t])
        print(f"\nham kayıt: {a.csv}")
    b.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
