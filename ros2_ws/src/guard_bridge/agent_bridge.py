#!/usr/bin/env python3
"""Köprünün ajan tarafı: RViz/LLM ve Nav2 → kartın ajan kanalı (K-040, protocol §10).

Kullanım (depo kökünden; bridge.launch.py ikisini birlikte başlatır):
    python3 ros2_ws/src/guard_bridge/agent_bridge.py --ros-args -p use_sim_time:=true

Karta giden:
- /goal_pose (PoseStamped, harita çerçevesi) → GOTO_CMD. Konum inancı (CONSISTENCY, RULES
  §3.4) o anki map → base_link'ten, okunduğu an kartın saatiyle (protocol §6.3): RViz'i
  kullanan insanın inancı aracın konumudur. LLM ajanı kendi okuduğu konumu verecek (4.3).
- /guard/task (std_msgs/String, JSON; ajan, Faz 4.2) → GOTO_CMD, WAIT_CMD, SPEED_LIMIT_CMD,
  STOP_CMD. Biçim convert.parse_task'ta; inancın ROS zamanı kartın saatine çevrilir (§6.3).
  Anlaşılamayan görev karta gitmez, ajana hata metni döner.
- /cmd_vel_nav (Nav2'nin hız komutu) → VELOCITY_CMD.
- HEARTBEAT 100 ms'de bir, arka planda. Bu düğüm durunca kart 500 ms'de HOLD'a geçer.
- /guard/reset servisi (std_srvs/Trigger) → RESET_CMD: kart açılışta HOLD'dadır,
  NORMAL'e yalnız bununla geçer (RULES §5). Cevap kartın kararıdır.
Karttan gelen:
- VERDICT → /guard/verdict (std_msgs/String, JSON; convert.verdict_text): her zaman tam.
- /guard/task'tan gelen komutun kararı → /guard/feedback (JSON: id, accepted, text). Metin
  "feedback" parametresine göre: full (D, varsayılan) gerekçe ve ipucuyla, minimal (C) yalnız
  "Komut reddedildi." (protocol §7.3, K-005). Coğrafi sınır ipucu güvenli noktanın adıyla.
- HEARTBEAT_ACK → kartın durumu, değiştiğinde günlüğe. STATUS → 10 s'de bir günlüğe ve her
  gelişinde (saniyede bir) /guard/status'a (JSON: durum, ret serisi, sayaçlar; Faz 5 kaydı, K-060).

Kablo çekilirse düğüm çökmez: "bağlantı yok" der, saniyede bir yeniden bağlanmayı
dener; kopukken gelen komutlar atılır. Yeniden bağlanınca kart HOLD'dadır (yeniden
başladı ya da kalp atışı kesildi, HOLD mandallı): NORMAL'e yine /guard/reset ile.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "shared" / "protocol" / "python"))
sys.path.insert(0, str(HERE.parents[2] / "tools"))

import convert as cv  # noqa: E402
import gen_site as gs  # noqa: E402
from ika_protocol import messages as m  # noqa: E402
from ika_protocol.link import AGENT_PORT, KEY_FILE, LINK_LOST, Heartbeat, Link, open_link  # noqa: E402

READ_PERIOD_S = 0.02
VERDICT_WAIT_S = 0.5
STATS_PERIOD_S = 10.0
RECONNECT_PERIOD_S = 1.0


class AgentBridge(Node):
    def __init__(self, key: bytes) -> None:
        super().__init__("agent_bridge")
        self.key = key
        self.link: Optional[Link] = None
        self.hb: Optional[Heartbeat] = None
        self.dropped = 0              # kopukken atılan komutlar
        self.verdicts = self.create_publisher(String, "/guard/verdict", 10)
        self.create_subscription(PoseStamped, "/goal_pose", self.on_goal_pose, 10)
        self.create_subscription(Twist, "/cmd_vel_nav", self.on_cmd_vel, 10)
        self.create_service(Trigger, "/guard/reset", self.on_reset)
        self.create_subscription(String, "/guard/task", self.on_task, 10)
        self.feedback = self.create_publisher(String, "/guard/feedback", 10)
        self.status_pub = self.create_publisher(String, "/guard/status", 10)
        mode = self.declare_parameter("feedback", "full").value
        if mode not in ("full", "minimal"):
            raise ValueError(f"feedback 'full' (D) ya da 'minimal' (C) olmalı, '{mode}' verildi")
        self.full_feedback = mode == "full"
        self.safe_points = gs.load_site()["safe"]     # ipucunu adlandırmak için (K-044)
        self.pending = {}                             # VERDICT'i beklenen sayaç → görev id'si
        self.state = None
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)
        self.last_status = None
        self.last_verdict = None
        self.velocity_sent = 0
        self.create_timer(READ_PERIOD_S, self.read)
        self.create_timer(STATS_PERIOD_S, self.stats)
        self.create_timer(RECONNECT_PERIOD_S, self.reconnect)
        self.reconnect()

    # -- bağlantı ------------------------------------------------------------

    def reconnect(self) -> None:
        if self.link is not None:
            return
        got = open_link(AGENT_PORT, m.Channel.AGENT, self.key)
        if got is None:
            return
        self.link, hello, how = got
        self.hb = Heartbeat(self.link)
        self.hb.start()
        self.get_logger().info(f"ajan kanalı: oturum 0x{hello.session_id:08X} ({how}), "
                               f"kart {hello.state.name}")

    def lost(self, why) -> None:
        self.get_logger().error(f"ajan kanalı koptu ({why}): yeniden bağlanılacak")
        if self.hb is not None:
            self.hb.stop()
        self.link.close()
        self.link, self.hb, self.state = None, None, None
        for task_id in self.pending.values():      # kararı gelmeyecek: ajana söylenir
            self.reply(task_id, False, "Kartla bağlantı koptu: komutun kararı alınamadı.")
        self.pending.clear()

    def send(self, msg) -> Optional[bytes]:
        """Gönderir; bağlantı yoksa ya da koparsa None."""
        if self.link is None:
            self.dropped += 1
            return None
        try:
            return self.link.send(msg)
        except LINK_LOST as e:
            self.lost(e)
            return None

    # -- karta ---------------------------------------------------------------

    def on_goal_pose(self, msg: PoseStamped) -> None:
        if msg.header.frame_id != "map":
            self.get_logger().warn(f"hedef '{msg.header.frame_id}' çerçevesinde, 'map' "
                                   "olmalı: gönderilmedi")
            return
        p, q = msg.pose.position, msg.pose.orientation
        x, y, yaw = cv.pose_to_cm(p.x, p.y, q.x, q.y, q.z, q.w)
        bx, by, bts = self.belief()
        wire = self.send(m.GotoCmd(x, y, yaw, bx, by, bts))
        if wire is None:
            self.get_logger().warn(f"bağlantı yok: hedef ({x}, {y}) cm gönderilmedi")
            return
        self.get_logger().info(f"GOTO_CMD #{Link.wire_seq(wire)}: ({x}, {y}) cm, {yaw} mrad")

    def belief(self):
        """Aracın konumu (map → base_link, cm) ve okunduğu an (kartın saati). Dönüşüm yoksa
        (0, 0, 0): kart BELIEF_TOO_OLD ile reddeder, karar kartta kalır."""
        if self.link is None:
            return 0, 0, 0
        try:
            t = self.tf.lookup_transform("map", "base_link", Time()).transform
        except TransformException as e:
            self.get_logger().warn(f"konum inancı okunamadı ({e}): 0 gönderiliyor")
            return 0, 0, 0
        r = t.rotation
        x, y, _ = cv.pose_to_cm(t.translation.x, t.translation.y, r.x, r.y, r.z, r.w)
        return x, y, self.link.board_now()

    def on_task(self, msg: String) -> None:
        try:
            task = cv.parse_task(msg.data)
        except cv.TaskError as e:
            self.reply(cv.task_id(msg.data), False, cv.task_error_text(e))
            self.get_logger().warn(f"görev anlaşılamadı ({e}): {msg.data[:120]}")
            return
        if self.link is None:
            self.reply(task["id"], False, "Kartla bağlantı yok: komut gönderilmedi.")
            return
        ts = 0
        if "belief" in task:
            now_s = self.get_clock().now().nanoseconds / 1e9
            ts = cv.ros_to_board_ms(task["belief"]["stamp"], now_s, self.link.board_now())
        kind, *args = cv.task_args(task, ts)
        cmd = {"git": m.GotoCmd, "bekle": m.WaitCmd, "hiz_siniri": m.SpeedLimitCmd,
               "dur": m.StopCmd}[kind](*args)
        wire = self.send(cmd)
        if wire is None:
            self.reply(task["id"], False, "Kartla bağlantı yok: komut gönderilmedi.")
            return
        seq = Link.wire_seq(wire)
        self.pending[seq] = task["id"]
        self.get_logger().info(f"görev {task['id']!r} → {cmd.NAME} #{seq} {args}")

    def reply(self, task_id: str, accepted: bool, text: str) -> None:
        self.feedback.publish(String(data=json.dumps(
            {"id": task_id, "accepted": accepted, "text": text}, ensure_ascii=False)))

    def on_cmd_vel(self, msg: Twist) -> None:
        if self.send(m.VelocityCmd(*cv.twist_to_cmd(msg.linear.x, msg.angular.z))) is not None:
            self.velocity_sent += 1

    def on_reset(self, _req, res: Trigger.Response) -> Trigger.Response:
        # Tek iş parçacıklı yürütücü: kararı burada okuruz, okuma zamanlayıcısı beklemez
        wire = self.send(m.ResetCmd())
        if wire is None:
            res.success, res.message = False, "bağlantı yok"
            return res
        seq = Link.wire_seq(wire)
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
        if self.link is None:
            return
        if not self.hb.alive():
            self.lost(self.hb.error)
            return
        try:
            frames = self.link.receive(0.005)
        except LINK_LOST as e:
            self.lost(e)
            return
        for f, cls in frames:
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
                self.status_pub.publish(String(data=json.dumps(
                    {**dataclasses.asdict(msg), "state": msg.state.name})))
            elif cls is m.Hello:
                if self.link.adopt_hello(f, msg):
                    self.get_logger().warn(f"yeni oturum 0x{msg.session_id:08X} (kart yeniden başladı)")

    def on_verdict(self, v: m.Verdict) -> None:
        self.last_verdict = v
        text = cv.verdict_text(*_verdict_fields(v))
        self.verdicts.publish(String(data=text))
        task_id = self.pending.pop(v.ref_seq, None)
        if task_id is not None:
            _, result, rule, reason, value, lo, hi, hx, hy = _verdict_fields(v)
            self.reply(task_id, v.result == m.Result.ACCEPTED,
                       cv.feedback_text(result, rule, reason, value, lo, hi, hx, hy,
                                        full=self.full_feedback, safe_points=self.safe_points))
        # rclpy aynı satırdan farklı düzeyde günlüğe izin vermez: iki ayrı çağrı
        if v.result == m.Result.ACCEPTED:
            self.get_logger().info(f"VERDICT {text}")
        else:
            self.get_logger().warn(f"VERDICT {text}")

    def stats(self) -> None:
        if self.link is None:
            self.get_logger().warn(f"bağlantı yok · atılan komut {self.dropped}")
            return
        s = self.last_status
        if s is None:
            self.get_logger().warn("STATUS gelmiyor")
            return
        self.get_logger().info(
            f"kart {s.state.name} · ret serisi {s.reject_streak} · VELOCITY_CMD {self.velocity_sent} "
            f"· kartta: ok {s.frames_ok}, auth {s.err_auth}, replay {s.err_replay}, "
            f"crc {s.err_crc}, framing {s.err_framing}, bayat {s.err_fresh}, kırpılan hız {s.clipped} "
            f"· PC'de bozuk çerçeve {self.link.rx_errors} · saat RTT {self.link.clock_rtt_ms()} ms")


def _verdict_fields(v: m.Verdict):
    return (v.ref_seq, v.result.name, v.rule.name, v.reason.name, v.value, v.lo, v.hi,
            v.hint_x_cm, v.hint_y_cm)


def main() -> int:
    # ROS Ctrl-C'de bağlamı kendisi kapatmasın: kalp atışı düzgün durdurulsun
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = AgentBridge(KEY_FILE.read_bytes())
    if node.link is None:
        node.get_logger().warn("ajan kanalı açılamadı: bekleniyor")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.hb is not None:
            node.hb.stop()   # kart 500 ms içinde HOLD'a geçer
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
