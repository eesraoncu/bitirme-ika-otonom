#!/usr/bin/env python3
"""Araç engele dayanınca konum tahmini ne kadar kopuyor (K-041 ölçütü).

Kullanım (simülasyon, Nav2, köprü açık; kart NORMAL'de):
    python3 tools/amcl_push_bench.py              # itme: monitörü atlar, 60 s konteynere iter
    python3 tools/amcl_push_bench.py --monitor    # monitörden geçer, 2 m geriden 25 s ileri

Her denemede araç Gazebo'da aynı yere konur (set_pose), AMCL'ye gerçek konum
/initialpose ile verilir, 0,3 m/s ileri komut gönderilir, sonra 10 s beklenir.
Hata: AMCL'nin map → base_link'i ile Gazebo'daki gerçek konum arasındaki fark
(haritanın dünyaya göre ≤ 0,8 m'lik hatası dahil, K-036).

- İtme: komut /cmd_vel_nav'a, yani monitörden SONRA girer; araç dayanır,
  tekerlekler boşa döner, odometri ilerleme sayar. Taban: en kötü 5,7–14 m.
- --monitor: komut /cmd_vel_raw'a, monitörden ÖNCE girer. Beklenen: araç
  konteynere değmeden durur (2026-10-08: 0,55 m boşluk, hata ≤ 0,16 m).
Hız komutları her iki durumda da karttan geçer.
"""
from __future__ import annotations

import argparse
import math
import re
import subprocess
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

MODEL = "ika_arac"
CONTAINER_SOUTH_Y = 3.28     # konteynerin güney yüzü (ika_saha.sdf: merkez y 4,5, en 2,44)
NOSE_M = 0.79                # base_link'ten burna (iz)
PUSH = dict(x=10.16, y=2.55, topic="/cmd_vel_nav", seconds=60.0)    # burun konteynere dayalı
MONITOR = dict(x=10.16, y=0.40, topic="/cmd_vel_raw", seconds=25.0)  # ~2 m boşluk
SPEED = 0.3
SAMPLE_S = 1.0
SETTLE_S = 10.0


def truth():
    """Gazebo'daki gerçek konum (x, y, yön). ign ara sıra boş çıktı verir: yeniden dene."""
    for _ in range(5):
        out = subprocess.run(["ign", "model", "-m", MODEL, "-p"], capture_output=True, text=True).stdout
        if "Pose" in out:
            break
    else:
        raise RuntimeError("Gazebo'dan konum okunamadı")
    nums = re.findall(r"\[([-0-9. ]+)\]", out.split("Pose")[1])
    x, y, _ = map(float, nums[0].split())
    return x, y, float(nums[1].split()[2])


def place(x: float, y: float, yaw: float) -> None:
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: 0.4}}, '
           f'orientation: {{z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    subprocess.run(["ign", "service", "-s", "/world/ika_saha/set_pose",
                    "--reqtype", "ignition.msgs.Pose", "--reptype", "ignition.msgs.Boolean",
                    "--timeout", "2000", "--req", req], capture_output=True, check=True)


def yaw_q(q) -> float:
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def ang_diff(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


class Bench(Node):
    def __init__(self, cmd_topic: str) -> None:
        super().__init__("amcl_push_bench",
                         parameter_overrides=[rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.cmd = self.create_publisher(Twist, cmd_topic, 10)
        self.init = self.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)

    def spin_for(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def drive(self, v: float) -> None:
        t = Twist()
        t.linear.x = float(v)
        self.cmd.publish(t)

    def amcl(self):
        r = self.tf.lookup_transform("map", "base_link", Time()).transform
        return r.translation.x, r.translation.y, yaw_q(r.rotation)

    def set_initial_pose(self, x: float, y: float, yaw: float) -> None:
        p = PoseWithCovarianceStamped()
        p.header.frame_id = "map"
        p.pose.pose.position.x, p.pose.pose.position.y = x, y
        p.pose.pose.orientation.z, p.pose.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        p.pose.covariance[0] = p.pose.covariance[7] = 0.05
        p.pose.covariance[35] = 0.02
        for _ in range(3):
            self.init.publish(p)
            self.spin_for(0.3)

    def error(self):
        t, a = truth(), self.amcl()
        return math.hypot(a[0] - t[0], a[1] - t[1]), math.degrees(ang_diff(a[2], t[2]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--monitor", action="store_true", help="collision_monitor'dan geçen deneme")
    args = ap.parse_args()
    cfg = MONITOR if args.monitor else PUSH

    rclpy.init()
    b = Bench(cfg["topic"])
    for _ in range(10):
        b.drive(0)
        b.spin_for(0.05)
    place(cfg["x"], cfg["y"], math.pi / 2)
    b.spin_for(1.0)
    b.set_initial_pose(*truth())
    b.spin_for(3.0)

    e0 = b.error()
    worst_m = worst_deg = 0.0
    gap_min = math.inf
    t0 = nxt = time.time()
    while time.time() - t0 < cfg["seconds"]:
        b.drive(SPEED)
        b.spin_for(0.05)
        if time.time() >= nxt:
            m, deg = b.error()
            worst_m, worst_deg = max(worst_m, m), max(worst_deg, deg)
            gap_min = min(gap_min, CONTAINER_SOUTH_Y - (truth()[1] + NOSE_M))
            nxt += SAMPLE_S
    for _ in range(10):
        b.drive(0)
        b.spin_for(0.05)
    b.spin_for(SETTLE_S)
    e1 = b.error()

    print(f"{'monitör' if args.monitor else 'itme'} ({cfg['topic']}, {cfg['seconds']:.0f} s)")
    print(f"  konteynere en az boşluk {max(gap_min, 0.0):.2f} m")
    print(f"  AMCL hatası: başta {e0[0]:.2f} m / {e0[1]:.0f}° · en kötü {worst_m:.2f} m / "
          f"{worst_deg:.0f}° · {SETTLE_S:.0f} s sonra {e1[0]:.2f} m / {e1[1]:.0f}°")
    b.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
