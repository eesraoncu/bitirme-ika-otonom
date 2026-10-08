#!/usr/bin/env python3
"""Köprünün araç tarafı: kartın araç kanalı ↔ Nav2 ve Gazebo (K-040, protocol §10).

Kullanım (depo kökünden; bridge.launch.py ikisini birlikte başlatır):
    python3 ros2_ws/src/guard_bridge/vehicle_bridge.py --ros-args -p use_sim_time:=true

Karttan gelen (CAN'den geçmiş, onaylı):
- GOAL  → Nav2'nin NavigateToPose eylemi (harita çerçevesi). Yeni hedef eskisinin yerine geçer.
- DRIVE → /cmd_vel (Gazebo). /cmd_vel'e yazan TEK düğüm budur (K-040 karar 1).
- HALT, SPEED_LIMIT_SET → şimdilik yalnızca günlüğe (kart tarafı Faz 4'te).
Karta giden:
- TELEMETRY 20 Hz: AMCL'nin map → base_link'i (K-040 karar 4). Dönüşüm yoksa gönderilmez.

Bekçi köpeği: DRIVE 0,5 s gelmezse ya da düğüm kapanırken /cmd_vel'e sıfır hız
yazılır. Gazebo'nun DiffDrive'ı son hızı süresiz uygular; kablo çıkarsa araç
son komutla gitmeye devam ederdi. Gerçek araçta bunu STM32 yapar (KTR §5).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "shared" / "protocol" / "python"))

import convert as cv  # noqa: E402
from ika_protocol import messages as m  # noqa: E402
from ika_protocol.link import KEY_FILE, VEHICLE_PORT, Link  # noqa: E402

TELEMETRY_PERIOD_S = 0.05     # 20 Hz (protocol §2)
READ_PERIOD_S = 0.02          # seri hattı okuma sıklığı
DRIVE_TIMEOUT_S = 0.5         # bu kadar DRIVE gelmezse sıfır hız
STATS_PERIOD_S = 10.0


class VehicleBridge(Node):
    def __init__(self, link: Link) -> None:
        super().__init__("vehicle_bridge")
        self.link = link
        self.cmd_vel = self.create_publisher(Twist, "/cmd_vel", 10)
        self.nav = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)
        self.last_drive = self.get_clock().now()
        self.moving = False           # son yayımlanan hız sıfırdan farklı mı
        self.goals = 0
        self.drives = 0
        self.telemetry_sent = 0
        self.create_timer(READ_PERIOD_S, self.read)
        self.create_timer(TELEMETRY_PERIOD_S, self.send_telemetry)
        self.create_timer(0.1, self.watchdog)
        self.create_timer(STATS_PERIOD_S, self.stats)

    # -- karttan -----------------------------------------------------------

    def read(self) -> None:
        for f, cls in self.link.receive(0.005):
            msg = cls.unpack(f.payload)
            if cls is m.Drive:
                self.on_drive(msg)
            elif cls is m.Goal:
                self.on_goal(msg)
            elif cls is m.Hello:
                self.on_hello(f, msg)
            elif cls in (m.Halt, m.SpeedLimitSet):
                self.get_logger().info(f"{cls.NAME} {msg} (Faz 4'te uygulanacak)")

    def on_drive(self, d: m.Drive) -> None:
        v, w = cv.cmd_to_twist(d.v_mm_s, d.w_mrad_s)
        self.publish_twist(v, w)
        self.last_drive = self.get_clock().now()
        self.drives += 1

    def on_goal(self, g: m.Goal) -> None:
        x, y, qz, qw = cv.cm_to_pose(g.x_cm, g.y_cm, g.yaw_mrad)
        if not self.nav.server_is_ready():
            self.get_logger().error(f"GOAL geldi ama Nav2 hazır değil: {g}")
            return
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = qz, qw
        self.nav.send_goal_async(goal)
        self.goals += 1
        self.get_logger().info(f"GOAL → Nav2: ({x:.2f}, {y:.2f}) m, {g.yaw_mrad} mrad, "
                               f"kaynak {g.source.name}")

    def on_hello(self, f, hello: m.Hello) -> None:
        # Kart yeniden başladıysa yeni oturum: sayaç ve saat ondan devam eder (protocol §5)
        if hello.session_id != self.link.session_id:
            with self.link.lock:
                self.link.session_id = hello.session_id
                self.link.seq = hello.last_rx_seq
                self.link.board_ms_at = (f.ts_ms, time.monotonic())
            self.get_logger().warn(f"yeni oturum 0x{hello.session_id:08X} (kart yeniden başladı)")

    # -- karta ---------------------------------------------------------------

    def send_telemetry(self) -> None:
        try:
            t = self.tf.lookup_transform("map", "base_link", Time())
        except TransformException:
            return    # AMCL henüz konum vermedi
        p, q = t.transform.translation, t.transform.rotation
        self.link.send(m.Telemetry(*cv.pose_to_cm(p.x, p.y, q.x, q.y, q.z, q.w)))
        self.telemetry_sent += 1

    # -- güvenlik ve kayıt ---------------------------------------------------

    def publish_twist(self, v: float, w: float) -> None:
        t = Twist()
        t.linear.x, t.angular.z = v, w
        self.cmd_vel.publish(t)
        self.moving = v != 0.0 or w != 0.0

    def watchdog(self) -> None:
        silent = (self.get_clock().now() - self.last_drive).nanoseconds / 1e9
        if self.moving and silent > DRIVE_TIMEOUT_S:
            self.publish_twist(0.0, 0.0)
            self.get_logger().warn(f"{silent:.1f} s DRIVE yok: araç durduruldu")

    def stats(self) -> None:
        self.get_logger().info(f"DRIVE {self.drives} · GOAL {self.goals} · "
                               f"TELEMETRY {self.telemetry_sent} · bozuk çerçeve {self.link.rx_errors}")


def main() -> int:
    key = KEY_FILE.read_bytes()
    link = Link(VEHICLE_PORT, m.Channel.VEHICLE, key, strict=False)
    hello, how = link.connect()
    # ROS Ctrl-C'de bağlamı kendisi kapatmasın: kapanırken sıfır hız yayımlanabilsin
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = VehicleBridge(link)
    node.get_logger().info(f"araç kanalı: oturum 0x{hello.session_id:08X} ({how}), "
                           f"kart {hello.state.name}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.publish_twist(0.0, 0.0)   # kapanırken araç dursun
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
