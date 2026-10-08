#!/usr/bin/env python3
"""Köprünün ajan tarafı: RViz/LLM ve Nav2 → kartın ajan kanalı (K-040, protocol §10).

Kullanım (depo kökünden; bridge.launch.py ikisini birlikte başlatır):
    python3 ros2_ws/src/guard_bridge/agent_bridge.py --ros-args -p use_sim_time:=true

Karta giden:
- /goal_pose (PoseStamped, harita çerçevesi) → GOTO_CMD. Konum inancı alanları 0 (Faz 4).
- /cmd_vel_nav (Nav2'nin hız komutu) → VELOCITY_CMD.
- HEARTBEAT 100 ms'de bir, arka planda. Bu düğüm durunca kart 500 ms'de HOLD'a geçer.
- /guard/reset servisi (std_srvs/Trigger) → RESET_CMD: kart açılışta HOLD'dadır,
  NORMAL'e yalnız bununla geçer (RULES §5). Cevap kartın kararıdır.
Karttan gelen:
- VERDICT → /guard/verdict (std_msgs/String, JSON; convert.verdict_text).
- HEARTBEAT_ACK → kartın durumu, değiştiğinde günlüğe. STATUS → 10 s'de bir günlüğe.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import String
from std_srvs.srv import Trigger

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "shared" / "protocol" / "python"))

import convert as cv  # noqa: E402
from ika_protocol import messages as m  # noqa: E402
from ika_protocol.link import AGENT_PORT, KEY_FILE, Heartbeat, Link  # noqa: E402

READ_PERIOD_S = 0.02
VERDICT_WAIT_S = 0.5
STATS_PERIOD_S = 10.0


class AgentBridge(Node):
    def __init__(self, link: Link) -> None:
        super().__init__("agent_bridge")
        self.link = link
        self.verdicts = self.create_publisher(String, "/guard/verdict", 10)
        self.create_subscription(PoseStamped, "/goal_pose", self.on_goal_pose, 10)
        self.create_subscription(Twist, "/cmd_vel_nav", self.on_cmd_vel, 10)
        self.create_service(Trigger, "/guard/reset", self.on_reset)
        self.state = None
        self.last_status = None
        self.last_verdict = None
        self.velocity_sent = 0
        self.create_timer(READ_PERIOD_S, self.read)
        self.create_timer(STATS_PERIOD_S, self.stats)

    # -- karta ---------------------------------------------------------------

    def on_goal_pose(self, msg: PoseStamped) -> None:
        if msg.header.frame_id != "map":
            self.get_logger().warn(f"hedef '{msg.header.frame_id}' çerçevesinde, 'map' "
                                   "olmalı: gönderilmedi")
            return
        p, q = msg.pose.position, msg.pose.orientation
        x, y, yaw = cv.pose_to_cm(p.x, p.y, q.x, q.y, q.z, q.w)
        seq = Link.wire_seq(self.link.send(m.GotoCmd(x, y, yaw, 0, 0, 0)))
        self.get_logger().info(f"GOTO_CMD #{seq}: ({x}, {y}) cm, {yaw} mrad")

    def on_cmd_vel(self, msg: Twist) -> None:
        self.link.send(m.VelocityCmd(*cv.twist_to_cmd(msg.linear.x, msg.angular.z)))
        self.velocity_sent += 1

    def on_reset(self, _req, res: Trigger.Response) -> Trigger.Response:
        # Tek iş parçacıklı yürütücü: kararı burada okuruz, okuma zamanlayıcısı beklemez
        seq = Link.wire_seq(self.link.send(m.ResetCmd()))
        self.last_verdict = None
        end = time.monotonic() + VERDICT_WAIT_S
        while time.monotonic() < end:
            self.read()
            v = self.last_verdict
            if v is not None and v.ref_seq == seq:
                res.success = v.result == m.Result.ACCEPTED
                res.message = cv.verdict_text(*_verdict_fields(v))
                return res
        res.success, res.message = False, "VERDICT gelmedi"
        return res

    # -- karttan -------------------------------------------------------------

    def read(self) -> None:
        for f, cls in self.link.receive(0.005):
            msg = cls.unpack(f.payload)
            if cls is m.Verdict:
                self.on_verdict(msg)
            elif cls is m.HeartbeatAck:
                if msg.state != self.state:
                    self.get_logger().info(f"kart: {msg.state.name}"
                                           + (f" (önce {self.state.name})" if self.state else ""))
                    self.state = msg.state
            elif cls is m.Status:
                self.last_status = msg
            elif cls is m.Hello:
                if self.link.adopt_hello(f, msg):
                    self.get_logger().warn(f"yeni oturum 0x{msg.session_id:08X} (kart yeniden başladı)")

    def on_verdict(self, v: m.Verdict) -> None:
        self.last_verdict = v
        text = cv.verdict_text(*_verdict_fields(v))
        self.verdicts.publish(String(data=text))
        # rclpy aynı satırdan farklı düzeyde günlüğe izin vermez: iki ayrı çağrı
        if v.result == m.Result.ACCEPTED:
            self.get_logger().info(f"VERDICT {text}")
        else:
            self.get_logger().warn(f"VERDICT {text}")

    def stats(self) -> None:
        s = self.last_status
        if s is None:
            self.get_logger().warn("STATUS gelmiyor")
            return
        self.get_logger().info(
            f"kart {s.state.name} · ret serisi {s.reject_streak} · VELOCITY_CMD {self.velocity_sent} "
            f"· kartta: ok {s.frames_ok}, auth {s.err_auth}, replay {s.err_replay}, "
            f"crc {s.err_crc}, framing {s.err_framing} · PC'de bozuk çerçeve {self.link.rx_errors}")


def _verdict_fields(v: m.Verdict):
    return (v.ref_seq, v.result.name, v.rule.name, v.reason.name, v.value, v.lo, v.hi,
            v.hint_x_cm, v.hint_y_cm)


def main() -> int:
    key = KEY_FILE.read_bytes()
    link = Link(AGENT_PORT, m.Channel.AGENT, key, strict=False)
    hello, how = link.connect()
    hb = Heartbeat(link)
    hb.start()
    # ROS Ctrl-C'de bağlamı kendisi kapatmasın: kalp atışı düzgün durdurulsun
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = AgentBridge(link)
    node.get_logger().info(f"ajan kanalı: oturum 0x{hello.session_id:08X} ({how}), "
                           f"kart {hello.state.name}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        hb.stop()   # kart 500 ms içinde HOLD'a geçer
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
