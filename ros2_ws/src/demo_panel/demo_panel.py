#!/usr/bin/env python3
"""Demo paneli (Faz 6, K-071): ajana görev, ajan ↔ kart konuşması, kart durumu, canlı saha, kamera.

Kullanım (depo kökünden; deney düzeni ve ajan açık):
    ros2 launch ros2_ws/src/experiments/launch/experiment.launch.py config:=D
    python3 ros2_ws/src/demo_panel/demo_panel.py --ros-args -p config:=D

Panel yalnız dinler; yazdığı iki şey: "Gönder" → /agent/task, "SIFIRLA" → /guard/reset.
- /agent/log: görev, geçersiz çağrı, bitti / vazgeçti (agent_core olayları).
- /guard/task → /guard/feedback (K-050): ajanın komutu ve kartın cevabı, canlı. Ret kuralı
  /guard/verdict'ten (köprü her yapılandırmada tam yazar): C'de ajan gerekçeyi görmez,
  izleyici görür. Karar ref_seq taşır, görev id'si değil: cevaptan hemen önceki ret kararı
  o cevabın kararı sayılır (VERDICT_MATCH_S).
- /guard/status: kart rozeti (A/B'de kart yok: "KART YOK").
- Aracın konumu TF'den (map → base_link, 10 Hz; ajan da böyle okur): /amcl_pose yalnız araç
  hareket edince yayımlanır, duran aracı panel hiç görmezdi. /odom (hız, sim saati), /plan,
  /scan (lidar, TF ile haritaya), /camera/image.
- Üst şeridin ışıkları: Sim (/odom geliyor mu), Nav2 (navigate_to_pose'un yayımcısı var mı),
  Ajan (/agent/task'ın dinleyicisi var mı), Kart (/guard/status geliyor mu).
- config parametresi (A/B/C/D) yalnız rozette yazılır; panelin davranışını değiştirmez.
ROS arka planda bir iş parçacığında döner, mesajları kuyruğa koyar; pencere kuyruğu 20 Hz'de
boşaltır (Qt nesnelerine yalnız kendi iş parçacığından dokunulur).
"""
from __future__ import annotations

import json
import math
import queue
import signal
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Optional

import rclpy
from nav_msgs.msg import Odometry, Path as NavPath
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from rclpy.utilities import remove_ros_args
from sensor_msgs.msg import Image, LaserScan
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener

from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                             QMainWindow, QPushButton, QSplitter, QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import map_style as ms   # noqa: E402
import panel_text as pt   # noqa: E402
import theme as th   # noqa: E402
from site_view import ROOT, SiteView   # noqa: E402
from widgets import Card, ChatView, Gauge, Light, StateBadge   # noqa: E402

VERDICT_MATCH_S = 1.0        # cevaptan en çok bu kadar önceki ret kararı o cevaba aittir
LIMITS_H = ROOT / "firmware" / "app" / "rules" / "limits" / "limits.h"
SCAN_STEP = 2                # lidarın her 2. ölçümü çizilir


def _yaw(q) -> float:
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class PanelNode(Node):
    """ROS tarafı: her mesaj (tür, veri) olarak kuyruğa. Yorum yok, çeviri pencerede."""

    def __init__(self, out: "queue.Queue") -> None:
        super().__init__("demo_panel")
        self.out = out
        self.config = str(self.declare_parameter("config", "").value).upper()
        json_topics = {"/agent/log": "log", "/guard/task": "task", "/guard/feedback": "feedback",
                       "/guard/verdict": "verdict", "/guard/status": "status"}
        for topic, kind in json_topics.items():
            self.create_subscription(String, topic, lambda m, k=kind: self._json(k, m.data), 50)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_timer(0.1, self._pose)
        self.create_timer(0.5, self._graph)
        self.create_subscription(Odometry, "/odom", self._odom, 10)
        self.create_subscription(NavPath, "/plan", self._plan, 10)
        self.create_subscription(LaserScan, "/scan", self._scan, qos_profile_sensor_data)
        self.create_subscription(Image, "/camera/image", self._image, qos_profile_sensor_data)
        self.task_pub = self.create_publisher(String, "/agent/task", 10)
        self.reset_cli = self.create_client(Trigger, "/guard/reset")

    def _json(self, kind: str, text: str) -> None:
        try:
            self.out.put((kind, json.loads(text)))
        except json.JSONDecodeError:
            pass

    def _lookup(self, frame: str):
        try:
            t = self.tf_buffer.lookup_transform("map", frame, Time()).transform
        except TransformException:
            return None                                 # AMCL henüz map'i yayımlamadı
        return t.translation.x, t.translation.y, _yaw(t.rotation)

    def _pose(self) -> None:
        pose = self._lookup("base_link")
        if pose:
            self.out.put(("pose", pose))

    def _graph(self) -> None:
        self.out.put(("graph", {
            "nav2": self.count_publishers("/navigate_to_pose/_action/status") > 0,
            "ajan": self.count_subscribers("/agent/task") > 0}))

    def _odom(self, m) -> None:
        stamp = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        self.out.put(("odom", (m.twist.twist.linear.x, stamp)))

    def _plan(self, m) -> None:
        self.out.put(("plan", [(s.pose.position.x, s.pose.position.y) for s in m.poses]))

    def _scan(self, m) -> None:
        pose = self._lookup(m.header.frame_id)
        if pose:
            self.out.put(("scan", ms.scan_points(m.ranges, m.angle_min, m.angle_increment,
                                                 m.range_min, m.range_max, pose, SCAN_STEP)))

    def _image(self, m) -> None:
        if m.encoding not in ("rgb8", "bgr8"):
            return
        img = QImage(bytes(m.data), m.width, m.height, m.step, QImage.Format_RGB888).copy()
        self.out.put(("image", img.rgbSwapped() if m.encoding == "bgr8" else img))

    def send_task(self, text: str) -> None:
        self.task_pub.publish(String(data=text))

    def reset(self) -> None:
        if not self.reset_cli.service_is_ready():
            self.out.put(("panel", "/guard/reset servisi yok: köprü açık mı?"))
            return
        fut = self.reset_cli.call_async(Trigger.Request())
        fut.add_done_callback(lambda f: self.out.put(
            ("panel", f"SIFIRLA {'tamam' if f.result().success else 'olmadı'}: {f.result().message}")))


class Panel(QMainWindow):
    def __init__(self, node: PanelNode, inbox: "queue.Queue") -> None:
        super().__init__()
        self.node, self.inbox = node, inbox
        self.status: Optional[dict] = None
        self.status_t: Optional[float] = None
        self.odom_t: Optional[float] = None
        self.graph: dict = {}
        self.last_reject: Optional[tuple] = None          # (zaman, karar)
        self.rules: Counter = Counter()                   # bu görevdeki retler, kurala göre
        self.pose = None
        limit = pt.speed_limit_from_header(LIMITS_H.read_text()) if LIMITS_H.exists() else None
        self.setWindowTitle("İKA bekçi kartı — demo paneli")
        self.resize(1560, 900)
        self.setStyleSheet(th.QSS)

        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())
        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 16)
        body.setSpacing(12)
        body.addLayout(self._task_row())

        self.view = SiteView()
        map_card = Card("Saha · canlı")
        map_card.body.addWidget(self.view, 1)

        self.badge = StateBadge()
        self.badge_hint = QLabel()
        self.badge_hint.setObjectName("hint")
        self.rule_chips = QLabel()
        self.rule_chips.setTextFormat(Qt.RichText)
        kart = Card("Bekçi kartı")
        kart.body.addWidget(self.badge)
        kart.body.addWidget(self.badge_hint)
        kart.body.addWidget(self.rule_chips)

        self.gauge = Gauge(limit)
        self.pos_label = QLabel("–")
        self.pos_label.setObjectName("value")
        self.yaw_label = QLabel("–")
        self.yaw_label.setObjectName("value")
        arac = Card("Araç")
        row = QHBoxLayout()
        row.addWidget(self.gauge, 1)
        facts = QGridLayout()
        for i, (name, w) in enumerate((("Konum", self.pos_label), ("Yön", self.yaw_label))):
            lab = QLabel(name)
            lab.setObjectName("hint")
            facts.addWidget(lab, 2 * i, 0)
            facts.addWidget(w, 2 * i + 1, 0)
        row.addLayout(facts)
        arac.body.addLayout(row)

        self.camera = QLabel("kamera bekleniyor")
        self.camera.setAlignment(Qt.AlignCenter)
        self.camera.setFixedHeight(210)
        self.camera.setStyleSheet(f"background: {th.MAP['outside']}; border-radius: 8px; color: {th.C['muted']};")
        kamera = Card("Ön kamera")
        kamera.body.addWidget(self.camera)

        self.chat = ChatView()
        konusma = Card("Ajan ↔ kart")
        konusma.body.addWidget(self.chat, 1)

        side = QWidget()
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(12)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(kart, 1)
        top_row.addWidget(arac, 1)
        sv.addLayout(top_row)
        sv.addWidget(kamera)
        sv.addWidget(konusma, 1)
        side.setMinimumWidth(560)

        split = QSplitter()
        split.addWidget(map_card)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        body.addWidget(split, 1)
        outer.addLayout(body, 1)
        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.tick()

    # ---- kurulum ------------------------------------------------------------------

    def _header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("header")
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 12, 20, 12)
        h.setSpacing(14)
        logo = QLabel("🛡️")
        logo.setStyleSheet("font-size: 28px;")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("İKA BEKÇİ KARTI")
        t.setObjectName("title")
        s = QLabel("LLM komutan · gömülü bekçi · otonom İKA")
        s.setObjectName("subtitle")
        titles.addWidget(t)
        titles.addWidget(s)
        h.addWidget(logo)
        h.addLayout(titles)
        label = pt.config_label(self.node.config)
        if label:
            chip = QLabel(f"Yapılandırma {label}")
            chip.setObjectName("chip")
            h.addWidget(chip)
        h.addStretch(1)
        self.lights = {name: Light(name) for name in ("Sim", "Nav2", "Ajan", "Kart")}
        for light in self.lights.values():
            h.addWidget(light)
        h.addSpacing(16)
        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        cap = QLabel("SİM SAATİ")
        cap.setObjectName("cardTitle")
        self.clock = QLabel("--:--")
        self.clock.setObjectName("clock")
        clock_box.addWidget(cap)
        clock_box.addWidget(self.clock)
        h.addLayout(clock_box)
        return bar

    def _task_row(self) -> QHBoxLayout:
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Ajana Türkçe bir görev yaz: ör. Kazı çukurunun ortasına in.")
        self.entry.returnPressed.connect(self.send)
        send = QPushButton("Gönder  ➤")
        send.setObjectName("primary")
        send.clicked.connect(self.send)
        reset = QPushButton("⟲  SIFIRLA")
        reset.setObjectName("danger")
        reset.setToolTip("Kartı NORMAL'e al (/guard/reset). Kart HOLD'da açılır.")
        reset.clicked.connect(self.node.reset)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.entry, 1)
        row.addWidget(send)
        row.addWidget(reset)
        return row

    # ---- olaylar --------------------------------------------------------------------

    def send(self) -> None:
        text = self.entry.text().strip()
        if text:
            self.node.send_task(text)
            self.entry.clear()

    def tick(self) -> None:
        while True:
            try:
                kind, data = self.inbox.get_nowait()
            except queue.Empty:
                break
            self.handle(kind, data)
        self.refresh()
        self.view.update()                     # animasyonlar (akan yol, halkalar) her karede

    def handle(self, kind: str, data) -> None:
        if kind == "log":
            if data.get("event") == "görev":
                self.chat.separator("yeni görev")
                self.view.clear_task()
                self.rules.clear()
            out = pt.log_bubble(data)
            if out:
                self.chat.add(*out)
        elif kind == "task":
            self.chat.add(*pt.task_bubble(data))
            if data.get("cmd") == "git":
                self.view.add_marker(data.get("id", ""), data.get("x", 0.0), data.get("y", 0.0),
                                     data.get("yer") or pt.point(data.get("x", 0.0), data.get("y", 0.0)),
                                     named=bool(data.get("yer")))
        elif kind == "verdict":
            if pt.is_rejection(data):
                self.last_reject = (time.monotonic(), data)
                self.rules[data.get("rule", "?")] += 1
        elif kind == "feedback":
            verdict = None
            if not data.get("accepted") and self.last_reject \
                    and time.monotonic() - self.last_reject[0] <= VERDICT_MATCH_S:
                verdict = self.last_reject[1]
                self.last_reject = None
            self.chat.add(*pt.feedback_bubble(data, verdict))
            hint = None
            if verdict and verdict.get("rule") == "GEOFENCE" and verdict.get("hint_m"):
                hint = tuple(verdict["hint_m"])
            self.view.resolve(data.get("id", ""), bool(data.get("accepted")), hint)
        elif kind == "status":
            self.status, self.status_t = data, time.monotonic()
        elif kind == "pose":
            self.pose = data
            self.view.set_vehicle(*data)
        elif kind == "odom":
            self.gauge.set_value(data[0])
            self.clock.setText(pt.clock(data[1]))
            self.odom_t = time.monotonic()
        elif kind == "graph":
            self.graph = data
        elif kind == "plan":
            self.view.path = data
        elif kind == "scan":
            self.view.scan = data
        elif kind == "image":
            self.show_camera(data)
        elif kind == "panel":
            self.chat.add("panel", "Panel", data)

    def show_camera(self, img: QImage) -> None:
        pix = QPixmap.fromImage(img).scaled(self.camera.width(), self.camera.height(),
                                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(QRectF(8, 8, 74, 22), 11, 11)
        p.setBrush(QColor(th.C["red"]))
        p.drawEllipse(QRectF(16, 14, 10, 10))
        f = QFont(th.FONT)
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(30, 8, 50, 22), Qt.AlignVCenter, "CANLI")
        p.end()
        self.camera.setPixmap(pix)

    def refresh(self) -> None:
        now = time.monotonic()
        age = None if self.status_t is None else now - self.status_t
        color, text = pt.badge(self.status, age)
        self.badge.set_state(color, text)
        hint = pt.BADGE_HINT.get(text, "")
        if self.status and age is not None and age <= pt.STATUS_STALE_S:
            hint += f" · üst üste ret {self.status.get('reject_streak', 0)}"
        self.badge_hint.setText(hint)
        chips = " ".join(f"<span style='background:{th.BUBBLE['ret'][0]}; color:{th.BUBBLE['ret'][2]};'>"
                         f"&nbsp;{rule} × {n}&nbsp;</span>" for rule, n in self.rules.most_common())
        self.rule_chips.setText(chips or f"<span style='color:{th.C['muted']}'>bu görevde ret yok</span>")
        if self.pose:
            self.pos_label.setText(f"{pt.point(self.pose[0], self.pose[1])} m")
            self.yaw_label.setText(f"{pt.num(math.degrees(self.pose[2]) % 360, 0)}°")
        self.lights["Sim"].set_state(pt.light(None if self.odom_t is None else now - self.odom_t))
        for name, key in (("Nav2", "nav2"), ("Ajan", "ajan")):
            self.lights[name].set_state("none" if key not in self.graph
                                        else "ok" if self.graph[key] else "stale")
        self.lights["Kart"].set_state(pt.light(age, pt.STATUS_STALE_S))
        for light in self.lights.values():
            light.update()                     # nabız animasyonu


def main() -> int:
    rclpy.init(args=sys.argv)
    inbox: "queue.Queue" = queue.Queue()
    node = PanelNode(inbox)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()

    signal.signal(signal.SIGINT, signal.SIG_DFL)          # Ctrl-C pencereyi de kapatsın
    app = QApplication(remove_ros_args(sys.argv))
    win = Panel(node, inbox)
    win.show()
    code = app.exec_()
    executor.shutdown()
    node.destroy_node()
    rclpy.try_shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
