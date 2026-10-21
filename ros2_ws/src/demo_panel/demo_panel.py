#!/usr/bin/env python3
"""Demo paneli (Faz 6): ajana görev, ajan ↔ kart konuşması, kart durumu, canlı saha, kamera.

Kullanım (depo kökünden; deney düzeni ve ajan açık):
    ros2 launch ros2_ws/src/experiments/launch/experiment.launch.py config:=D
    python3 ros2_ws/src/demo_panel/demo_panel.py

Panel yalnız dinler; yazdığı iki şey: "Gönder" → /agent/task, "SIFIRLA" → /guard/reset.
- /agent/log: görev, geçersiz çağrı, bitti / vazgeçti (agent_core olayları).
- /guard/task → /guard/feedback (K-050): ajanın komutu ve kartın cevabı, canlı. Ret kuralı
  /guard/verdict'ten (köprü her yapılandırmada tam yazar): C'de ajan gerekçeyi görmez,
  izleyici görür. Karar ref_seq taşır, görev id'si değil: cevaptan hemen önceki ret kararı
  o cevabın kararı sayılır (VERDICT_MATCH_S).
- /guard/status: kart rozeti (A/B'de kart yok: "KART YOK").
- Aracın konumu TF'den (map → base_link, 10 Hz; ajan da böyle okur): /amcl_pose yalnız araç
  hareket edince yayımlanır, duran aracı panel hiç görmezdi. /odom (hız), /plan, /camera/image.
ROS arka planda bir iş parçacığında döner, mesajları kuyruğa koyar; pencere kuyruğu 10 Hz'de
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
from html import escape
from pathlib import Path
from typing import Optional

import rclpy
from nav_msgs.msg import Odometry, Path as NavPath
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from rclpy.utilities import remove_ros_args
from sensor_msgs.msg import Image
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                             QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import panel_text as pt   # noqa: E402
from site_view import SiteView   # noqa: E402

VERDICT_MATCH_S = 1.0        # cevaptan en çok bu kadar önceki ret kararı o cevaba aittir
LINE_COLOR = {"gorev": "#111111", "komut": "#2a4d8f", "kabul": "#1f7a45", "ret": "#c62828",
              "gecersiz": "#a15c00", "son": "#111111", "uyari": "#a15c00", "panel": "#6b6b6b"}


def _yaw(q) -> float:
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class PanelNode(Node):
    """ROS tarafı: her mesaj (tür, veri) olarak kuyruğa. Yorum yok, çeviri pencerede."""

    def __init__(self, out: "queue.Queue") -> None:
        super().__init__("demo_panel")
        self.out = out
        json_topics = {"/agent/log": "log", "/guard/task": "task", "/guard/feedback": "feedback",
                       "/guard/verdict": "verdict", "/guard/status": "status"}
        for topic, kind in json_topics.items():
            self.create_subscription(String, topic, lambda m, k=kind: self._json(k, m.data), 50)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_timer(0.1, self._pose)
        self.create_subscription(Odometry, "/odom", self._odom, 10)
        self.create_subscription(NavPath, "/plan", self._plan, 10)
        self.create_subscription(Image, "/camera/image", self._image, qos_profile_sensor_data)
        self.task_pub = self.create_publisher(String, "/agent/task", 10)
        self.reset_cli = self.create_client(Trigger, "/guard/reset")

    def _json(self, kind: str, text: str) -> None:
        try:
            self.out.put((kind, json.loads(text)))
        except json.JSONDecodeError:
            pass

    def _pose(self) -> None:
        try:
            t = self.tf_buffer.lookup_transform("map", "base_link", Time()).transform
        except TransformException:
            return                                  # AMCL henüz map'i yayımlamadı
        self.out.put(("pose", (t.translation.x, t.translation.y, _yaw(t.rotation))))

    def _odom(self, m) -> None:
        self.out.put(("speed", m.twist.twist.linear.x))

    def _plan(self, m) -> None:
        self.out.put(("plan", [(s.pose.position.x, s.pose.position.y) for s in m.poses]))

    def _image(self, m) -> None:
        if m.encoding not in ("rgb8", "bgr8"):
            return
        img = QImage(bytes(m.data), m.width, m.height, m.step, QImage.Format_RGB888).copy()
        self.out.put(("image", img.rgbSwapped() if m.encoding == "bgr8" else img))

    def send_task(self, text: str) -> None:
        self.task_pub.publish(String(data=text))

    def reset(self) -> None:
        if not self.reset_cli.service_is_ready():
            self.out.put(("panel", "SIFIRLA: /guard/reset servisi yok (köprü açık mı?)"))
            return
        fut = self.reset_cli.call_async(Trigger.Request())
        fut.add_done_callback(lambda f: self.out.put(
            ("panel", f"SIFIRLA: {'tamam' if f.result().success else 'olmadı'} — {f.result().message}")))


class Panel(QMainWindow):
    def __init__(self, node: PanelNode, inbox: "queue.Queue") -> None:
        super().__init__()
        self.node, self.inbox = node, inbox
        self.status: Optional[dict] = None
        self.status_t: Optional[float] = None
        self.last_reject: Optional[tuple] = None          # (zaman, karar)
        self.speed = 0.0
        self.pose = None
        self.setWindowTitle("İKA bekçi kartı — demo paneli")
        self.resize(1400, 820)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Ajana görev yaz: ör. Kazı çukurunun ortasına in.")
        self.entry.returnPressed.connect(self.send)
        send = QPushButton("Gönder")
        send.clicked.connect(self.send)
        reset = QPushButton("SIFIRLA")
        reset.setToolTip("Kartı NORMAL'e al (/guard/reset). Kart HOLD'da açılır.")
        reset.clicked.connect(self.node.reset)
        top = QHBoxLayout()
        top.addWidget(QLabel("Görev:"))
        top.addWidget(self.entry, 1)
        top.addWidget(send)
        top.addWidget(reset)

        self.view = SiteView()
        self.badge = QLabel()
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setMinimumHeight(48)
        self.info = QLabel()
        self.info.setStyleSheet("font-size: 14px;")
        self.camera = QLabel("kamera görüntüsü bekleniyor")
        self.camera.setAlignment(Qt.AlignCenter)
        self.camera.setFixedHeight(220)
        self.camera.setStyleSheet("background: #222; color: #aaa;")
        self.log = QTextBrowser()
        self.log.setStyleSheet("font-size: 14px;")

        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Kart</b>"))
        right.addWidget(self.badge)
        right.addWidget(self.info)
        right.addWidget(self.camera)
        right.addWidget(QLabel("<b>Ajan ↔ kart</b>"))
        right.addWidget(self.log, 1)
        side = QWidget()
        side.setLayout(right)
        split = QSplitter()
        split.addWidget(self.view)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        body = QVBoxLayout()
        body.addLayout(top)
        body.addWidget(split, 1)
        root = QWidget()
        root.setLayout(body)
        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drain)
        self.timer.start(100)
        self.refresh_badge()

    # ---- olaylar --------------------------------------------------------------------

    def send(self) -> None:
        text = self.entry.text().strip()
        if text:
            self.node.send_task(text)
            self.entry.clear()

    def line(self, text: str, kind: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        color = LINE_COLOR.get(kind, "#111111")
        weight = "bold" if kind in ("gorev", "ret", "kabul", "son") else "normal"
        self.log.append(f'<span style="color:#888">{stamp}</span>&nbsp; '
                        f'<span style="color:{color}; font-weight:{weight}">{escape(text)}</span>')

    def drain(self) -> None:
        changed = False
        while True:
            try:
                kind, data = self.inbox.get_nowait()
            except queue.Empty:
                break
            changed |= self.handle(kind, data)
        self.refresh_badge()
        if changed:
            self.view.update()

    def handle(self, kind: str, data) -> bool:
        """Bir mesajı işler; harita yeniden çizilmeli mi döndürür."""
        if kind == "log":
            out = pt.log_line(data)
            if data.get("event") == "görev":
                self.log.append("<hr>")
                self.view.clear_task()
            if out:
                self.line(*out)
            return data.get("event") == "görev"
        if kind == "task":
            self.line(f"Ajan → kart: {pt.task_line(data)}", "komut")
            if data.get("cmd") == "git":
                self.view.add_marker(data.get("id", ""), data.get("x", 0.0), data.get("y", 0.0),
                                     data.get("yer") or pt.point(data.get("x", 0.0), data.get("y", 0.0)))
                return True
            return False
        if kind == "verdict":
            if pt.is_rejection(data):
                self.last_reject = (time.monotonic(), data)
            return False
        if kind == "feedback":
            verdict = None
            if not data.get("accepted") and self.last_reject \
                    and time.monotonic() - self.last_reject[0] <= VERDICT_MATCH_S:
                verdict = self.last_reject[1]
                self.last_reject = None
            text, k = pt.feedback_line(data, verdict)
            self.line(f"Kart → ajan: {text}", k)
            hint = None
            if verdict and verdict.get("rule") == "GEOFENCE" and verdict.get("hint_m"):
                hint = tuple(verdict["hint_m"])
            self.view.resolve(data.get("id", ""), bool(data.get("accepted")), hint)
            return True
        if kind == "status":
            self.status, self.status_t = data, time.monotonic()
            return False
        if kind == "pose":
            self.pose = data
            self.view.vehicle = data
            return True
        if kind == "speed":
            self.speed = data
            return False
        if kind == "plan":
            self.view.path = data
            return True
        if kind == "image":
            self.camera.setPixmap(QPixmap.fromImage(data).scaled(
                self.camera.width(), self.camera.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            return False
        if kind == "panel":
            self.line(data, "panel")
        return False

    def refresh_badge(self) -> None:
        age = None if self.status_t is None else time.monotonic() - self.status_t
        color, text = pt.badge(self.status, age)
        self.badge.setText(text)
        self.badge.setStyleSheet(f"background:{color}; color:white; font-size:22px; "
                                 f"font-weight:bold; border-radius:6px;")
        parts = [f"Hız: {pt.num(self.speed, 2)} m/s"]
        if self.pose:
            parts.append(f"Konum: {pt.point(self.pose[0], self.pose[1])} m")
        if self.status and age is not None and age <= pt.STATUS_STALE_S:
            parts.append(f"Üst üste ret: {self.status.get('reject_streak', 0)}")
        self.info.setText("   ·   ".join(parts))


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
