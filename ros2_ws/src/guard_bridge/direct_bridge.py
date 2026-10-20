#!/usr/bin/env python3
"""Kartsız köprü: A ve B yapılandırmaları (K-054). Kart yolda değil, köprü görevi ve hızı
doğrudan Nav2'ye ve araca verir. Ajan aynı arayüzü görür (/guard/task, /guard/feedback).

Kullanım (depo kökünden; bridge.launch.py guard:=false başlatır):
    python3 ros2_ws/src/guard_bridge/direct_bridge.py --ros-args -p use_sim_time:=true

agent_bridge + kart + vehicle_bridge'in yerine geçer:
- /guard/task (JSON, convert.parse_task) → git: Nav2 hedefi, kartlı yoldaki yuvarlamayla;
  bekle ve dur: Nav2 hedefi iptal (kartlı yolda WAIT/STOP → HALT → iptal, K-042);
  hiz_siniri: /speed_limit (LIMIT denetimi yok). convert.direct_action.
  Geçerli her görev kabul edilir: /guard/feedback "Komut kabul edildi." (D'deki kabul metni).
  Anlaşılamayan görev: kartlı köprüdeki hata metni.
- /goal_pose (RViz, ölçüm betikleri) → Nav2 hedefi.
- /cmd_vel_nav → /cmd_vel. /cmd_vel'e yazan TEK düğüm budur (K-040 karar 1).
- /guard/reset: başarı döner (sıfırlanacak kart yok), koşu düzeneği dört yapılandırmada aynı.
Kart kararı yok: /guard/verdict yayımlanmaz.

Bekçi köpeği: /cmd_vel_nav 0,5 s gelmezse /cmd_vel'e sıfır, vehicle_bridge'deki gibi (Gazebo'nun
DiffDrive'ı son hızı süresiz uygular). Bu düğüm dondurulursa (agent_freeze_1) bekçi köpeği de
donar, araç son hızla gider: A/B'de ölçülen bu (K-058).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.msg import SpeedLimit
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import String
from std_srvs.srv import Trigger

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import convert as cv  # noqa: E402
from nav2_goal import Nav2Goal  # noqa: E402

VELOCITY_TIMEOUT_S = 0.5      # vehicle_bridge'in DRIVE_TIMEOUT_S'i
STATS_PERIOD_S = 10.0
ACCEPTED = cv.feedback_text("ACCEPTED", "NONE", "NONE", 0, 0, 0, 0, 0, full=True)


class DirectBridge(Node):
    def __init__(self) -> None:
        super().__init__("direct_bridge")
        self.nav = Nav2Goal(self)
        self.cmd_vel = self.create_publisher(Twist, "/cmd_vel", 10)
        self.speed_limit = self.create_publisher(SpeedLimit, "/speed_limit", 10)
        self.feedback = self.create_publisher(String, "/guard/feedback", 10)
        self.create_subscription(String, "/guard/task", self.on_task, 10)
        self.create_subscription(PoseStamped, "/goal_pose", self.on_goal_pose, 10)
        self.create_subscription(Twist, "/cmd_vel_nav", self.on_cmd_vel, 10)
        self.create_service(Trigger, "/guard/reset", self.on_reset)
        self.last_cmd = self.get_clock().now()
        self.moving = False
        self.tasks = 0
        self.velocities = 0
        self.create_timer(0.1, self.watchdog)
        self.create_timer(STATS_PERIOD_S, self.stats)
        self.get_logger().info("kartsız köprü (A/B): görevler doğrudan Nav2'ye")

    # -- görev ve hedef --------------------------------------------------------

    def on_task(self, msg: String) -> None:
        try:
            task = cv.parse_task(msg.data)
        except cv.TaskError as e:
            self.reply(cv.task_id(msg.data), False, cv.task_error_text(e))
            self.get_logger().warn(f"görev anlaşılamadı ({e}): {msg.data[:120]}")
            return
        action = cv.direct_action(task)
        if action[0] == "hedef":
            if not self.goal(*action[1:]):
                self.reply(task["id"], False, "Nav2 hazır değil: komut gönderilmedi.")
                return
        elif action[0] == "hiz_siniri":
            self.publish_speed_limit(action[1])
        else:
            self.nav.cancel(task["cmd"])
        self.tasks += 1
        self.reply(task["id"], True, ACCEPTED)
        self.get_logger().info(f"görev {task['id']!r} {task['cmd']} → {action}")

    def on_goal_pose(self, msg: PoseStamped) -> None:
        if msg.header.frame_id != "map":
            self.get_logger().warn(f"hedef '{msg.header.frame_id}' çerçevesinde, 'map' "
                                   "olmalı: gönderilmedi")
            return
        p, q = msg.pose.position, msg.pose.orientation
        self.goal(*cv.cm_to_pose(*cv.pose_to_cm(p.x, p.y, q.x, q.y, q.z, q.w)))

    def goal(self, x: float, y: float, qz: float, qw: float) -> bool:
        if not self.nav.ready():
            self.get_logger().error(f"Nav2 hazır değil: hedef ({x:.2f}, {y:.2f}) gönderilmedi")
            return False
        self.nav.send(x, y, qz, qw)
        self.get_logger().info(f"hedef → Nav2: ({x:.2f}, {y:.2f}) m")
        return True

    def publish_speed_limit(self, mps: float) -> None:
        msg = SpeedLimit()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.percentage = False
        msg.speed_limit = mps
        self.speed_limit.publish(msg)
        self.get_logger().info(f"hız sınırı → Nav2: {mps:.3f} m/s")

    def reply(self, task_id: str, accepted: bool, text: str) -> None:
        self.feedback.publish(String(data=json.dumps(
            {"id": task_id, "accepted": accepted, "text": text}, ensure_ascii=False)))

    def on_reset(self, _req, res: Trigger.Response) -> Trigger.Response:
        res.success, res.message = True, "kart yok (A/B): sıfırlanacak bir şey yok"
        return res

    # -- hız -----------------------------------------------------------------

    def on_cmd_vel(self, msg: Twist) -> None:
        self.publish_twist(msg.linear.x, msg.angular.z)
        self.last_cmd = self.get_clock().now()
        self.velocities += 1

    def publish_twist(self, v: float, w: float) -> None:
        t = Twist()
        t.linear.x, t.angular.z = v, w
        self.cmd_vel.publish(t)
        self.moving = v != 0.0 or w != 0.0

    def watchdog(self) -> None:
        silent = (self.get_clock().now() - self.last_cmd).nanoseconds / 1e9
        if self.moving and silent > VELOCITY_TIMEOUT_S:
            self.publish_twist(0.0, 0.0)
            self.get_logger().warn(f"{silent:.1f} s hız komutu yok: araç durduruldu")

    def stats(self) -> None:
        self.get_logger().info(f"görev {self.tasks} · hız komutu {self.velocities}")


def main() -> int:
    # ROS Ctrl-C'de bağlamı kendisi kapatmasın: kapanırken sıfır hız yayımlanabilsin
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = DirectBridge()
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
