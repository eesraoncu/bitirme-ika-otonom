"""Kuşbakışı saha çizimi (Qt): Nav2 haritası + saha bölgeleri + canlı araç, yol ve hedefler.

Arka plan: ros2_ws/src/ika_nav/maps/ika_saha.{yaml,pgm} (Nav2'nin kayıtlı haritası).
Bölgeler: shared/site/ika_saha.yaml (tek kaynak, K-037): yasak bölgeler GERÇEK sınırlarıyla
(paysız), güvenli noktalar ve ajanın yer adları. Aracın izi Nav2'nin footprint'inden
(ika_nav/config/nav2_params.yaml). Hiçbir koordinat ya da ölçü burada elle yazılmaz.
Çizim harita pikselinde yapılır (panel_text.world_to_px); pencereye sığacak kadar ölçeklenir.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

import panel_text as pt

ROOT = Path(__file__).resolve().parents[3]
MAP_YAML = ROOT / "ros2_ws" / "src" / "ika_nav" / "maps" / "ika_saha.yaml"
SITE_YAML = ROOT / "shared" / "site" / "ika_saha.yaml"
NAV2_YAML = ROOT / "ros2_ws" / "src" / "ika_nav" / "config" / "nav2_params.yaml"

FORBIDDEN = QColor(198, 40, 40, 90)
SAFE = QColor("#1f9d55")
PLACE = QColor("#2a78d6")
PATH = QColor("#2a78d6")
VEHICLE = QColor("#111111")


class Marker:
    """Ajanın karta gönderdiği bir hedef: önce 'bekliyor', kartın cevabıyla 'kabul' ya da 'ret'.
    Rette ipucu (en yakın güvenli nokta) varsa oraya kesik çizgi çekilir."""

    def __init__(self, task_id: str, x: float, y: float, label: str) -> None:
        self.task_id, self.x, self.y, self.label = task_id, x, y, label
        self.state = "bekliyor"
        self.hint: Optional[Tuple[float, float]] = None


class SiteView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        meta = yaml.safe_load(MAP_YAML.read_text())
        self.image = QImage(str(MAP_YAML.parent / meta["image"]))
        self.res = float(meta["resolution"])
        self.origin = (float(meta["origin"][0]), float(meta["origin"][1]))
        self.site = yaml.safe_load(SITE_YAML.read_text())
        nav2 = yaml.safe_load(NAV2_YAML.read_text())
        fp = nav2["local_costmap"]["local_costmap"]["ros__parameters"]["footprint"]
        self.footprint = yaml.safe_load(fp) if isinstance(fp, str) else fp   # [[x, y], ...] m, araç çerçevesi
        self.vehicle: Optional[Tuple[float, float, float]] = None     # x, y (m), yön (rad)
        self.path: List[Tuple[float, float]] = []
        self.markers: List[Marker] = []
        self.setMinimumSize(520, 340)

    # ---- durum (panel çağırır, sonra update()) --------------------------------------

    def add_marker(self, task_id: str, x: float, y: float, label: str) -> None:
        self.markers = [mk for mk in self.markers if mk.task_id != task_id][-11:]   # son 12 hedef
        self.markers.append(Marker(task_id, x, y, label))

    def resolve(self, task_id: str, accepted: bool, hint: Optional[Tuple[float, float]]) -> None:
        for mk in self.markers:
            if mk.task_id == task_id:
                mk.state = "kabul" if accepted else "ret"
                mk.hint = None if accepted else hint

    def clear_task(self) -> None:
        """Yeni görev: önceki hedefler ve yol silinir."""
        self.markers, self.path = [], []

    # ---- çizim --------------------------------------------------------------------

    def px(self, x: float, y: float) -> QPointF:
        return QPointF(*pt.world_to_px(x, y, self.origin, self.res, self.image.height()))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#f4f3ef"))
        w, h = self.image.width(), self.image.height()
        k = min(self.width() / w, self.height() / h)                  # en-boy oranı korunur
        p.translate((self.width() - w * k) / 2, (self.height() - h * k) / 2)
        p.scale(k, k)
        p.drawImage(0, 0, self.image)
        unit = 1 / k                                                  # 1 ekran pikseli, harita pikselinde
        try:
            self._zones(p, unit)
            self._path(p, unit)
            self._markers(p, unit)
            self._vehicle(p, unit)
        finally:
            p.end()                             # çizimde hata olsa da çizici kapanır

    def _label(self, p: QPainter, at: QPointF, text: str, color: QColor, unit: float) -> None:
        font = QFont()
        font.setPointSizeF(9 * unit)
        p.setFont(font)
        p.setPen(color)
        p.drawText(at + QPointF(6 * unit, -6 * unit), text)

    def _zones(self, p: QPainter, unit: float) -> None:
        p.setPen(QPen(QColor("#555555"), 1.5 * unit, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF([self.px(*c) for c in self.site["allowed"]]))
        for name, poly in self.site["forbidden"].items():
            p.setPen(QPen(QColor("#c62828"), 1.5 * unit))
            p.setBrush(QBrush(FORBIDDEN))
            pts = [self.px(*c) for c in poly]
            p.drawPolygon(QPolygonF(pts))
            cx = sum(q.x() for q in pts) / len(pts)
            cy = sum(q.y() for q in pts) / len(pts)
            self._label(p, QPointF(cx - 20 * unit, cy + 10 * unit), name, QColor("#8e1b1b"), unit)
        for name, (x, y) in self.site["safe_points"].items():
            self._dot(p, self.px(x, y), SAFE, 4 * unit)
            self._label(p, self.px(x, y), name, SAFE, unit)
        for name, xyd in self.site.get("places", {}).items():    # [x, y, varış yönü (derece)]
            x, y = xyd[0], xyd[1]
            self._dot(p, self.px(x, y), PLACE, 3 * unit)
            self._label(p, self.px(x, y), name, PLACE, unit)

    @staticmethod
    def _dot(p: QPainter, at: QPointF, color: QColor, r: float) -> None:
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(color))
        p.drawEllipse(at, r, r)

    def _path(self, p: QPainter, unit: float) -> None:
        if len(self.path) < 2:
            return
        p.setPen(QPen(PATH, 2.5 * unit))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([self.px(x, y) for x, y in self.path]))

    def _markers(self, p: QPainter, unit: float) -> None:
        for mk in self.markers:
            at = self.px(mk.x, mk.y)
            if mk.state == "ret":
                if mk.hint is not None:
                    p.setPen(QPen(QColor("#c62828"), 1.5 * unit, Qt.DashLine))
                    p.drawLine(at, self.px(*mk.hint))
                p.setPen(QPen(QColor("#c62828"), 3.5 * unit))
                d = 7 * unit
                p.drawLine(at + QPointF(-d, -d), at + QPointF(d, d))
                p.drawLine(at + QPointF(-d, d), at + QPointF(d, -d))
                self._label(p, at, mk.label, QColor("#c62828"), unit)
            else:
                color = SAFE if mk.state == "kabul" else QColor("#888888")
                p.setPen(QPen(color, 2.5 * unit))
                p.drawLine(at, at + QPointF(0, -18 * unit))               # bayrak direği
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawPolygon(QPolygonF([at + QPointF(0, -18 * unit), at + QPointF(12 * unit, -14 * unit),
                                         at + QPointF(0, -10 * unit)]))
                self._label(p, at + QPointF(8 * unit, 18 * unit), mk.label, color, unit)   # yer adının altına

    def _vehicle(self, p: QPainter, unit: float) -> None:
        if self.vehicle is None:
            return
        x, y, yaw = self.vehicle
        at = self.px(x, y)
        p.save()
        p.translate(at)
        p.rotate(-math.degrees(yaw))            # harita pikselinde y aşağı: açı ters yönde
        s = 1 / self.res                        # 1 m, harita pikselinde
        p.setPen(QPen(QColor("white"), 1.5 * unit))
        p.setBrush(QBrush(VEHICLE))
        p.drawPolygon(QPolygonF([QPointF(fx * s, -fy * s) for fx, fy in self.footprint]))
        front = max(fx for fx, _ in self.footprint) * s
        p.setPen(QPen(QColor("#f2c94c"), 3 * unit))   # yön çizgisi: merkezden öne
        p.drawLine(QPointF(0, 0), QPointF(front, 0))
        p.restore()
