"""Kuşbakışı saha (Qt): stilize harita + saha bölgeleri + canlı araç, iz, lidar, yol ve hedefler.

Arka plan: Nav2'nin kayıtlı haritası (ros2_ws/src/ika_nav/maps/ika_saha.{yaml,pgm}), ham gri
görüntü yerine sınıflarıyla (map_style.classify): asfalt zemin, engel, bilinmeyen.
Bölgeler: shared/site/ika_saha.yaml (tek kaynak, K-037): yasak bölgeler GERÇEK sınırlarıyla
(paysız), güvenli noktalar ve ajanın yer adları. Aracın izi Nav2'nin footprint'inden
(ika_nav/config/nav2_params.yaml). Hiçbir koordinat ya da ölçü burada elle yazılmaz.
Çizim ekran pikselinde: harita pencereye en-boy oranı korunarak sığdırılır (to_screen).
Animasyonlar (akan yol, ret halkası, hedef nabzı) zamana bağlı; panel 20 Hz'de yeniden çizer.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import yaml
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

import map_style as ms
import panel_text as pt
import theme as th

ROOT = Path(__file__).resolve().parents[3]
MAP_YAML = ROOT / "ros2_ws" / "src" / "ika_nav" / "maps" / "ika_saha.yaml"
SITE_YAML = ROOT / "shared" / "site" / "ika_saha.yaml"
NAV2_YAML = ROOT / "ros2_ws" / "src" / "ika_nav" / "config" / "nav2_params.yaml"

TRINARY_UNKNOWN = 205    # map_saver trinary'de haritalanmamış hücre (map_style'daki not)
GRID_M = 5.0              # ızgara aralığı ve ölçek çubuğu
TRAIL_MAX = 600           # izde tutulan en çok nokta
TRAIL_STEP_M = 0.10       # iz noktaları arası en az mesafe
REJECT_PULSE_S = 1.2      # retten sonraki yayılan halkanın bir turu
REJECT_PULSES = 4


def _qc(key: str, alpha: float = 1.0) -> QColor:
    c = QColor(th.MAP.get(key, th.C.get(key, key)))
    c.setAlphaF(alpha)
    return c


class Marker:
    """Ajanın karta gönderdiği bir hedef: önce 'bekliyor', kartın cevabıyla 'kabul' ya da 'ret'.
    Rette ipucu (en yakın güvenli nokta) varsa oraya ok çizilir."""

    def __init__(self, task_id: str, x: float, y: float, label: str, named: bool = False) -> None:
        self.task_id, self.x, self.y, self.label = task_id, x, y, label
        self.named = named                     # yer adıyla verildi: ad haritada zaten yazılı
        self.state = "bekliyor"
        self.hint: Optional[Tuple[float, float]] = None
        self.t = time.monotonic()


class SiteView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        meta = yaml.safe_load(MAP_YAML.read_text())
        self.res = float(meta["resolution"])
        self.origin = (float(meta["origin"][0]), float(meta["origin"][1]))
        unknown = TRINARY_UNKNOWN if meta.get("mode") == "trinary" else None
        classes = ms.classify(ms.read_pgm(MAP_YAML.parent / meta["image"]), int(meta.get("negate", 0)),
                              float(meta["occupied_thresh"]), float(meta["free_thresh"]), unknown)
        self.image = self._render(classes)
        self.site = yaml.safe_load(SITE_YAML.read_text())
        nav2 = yaml.safe_load(NAV2_YAML.read_text())
        fp = nav2["local_costmap"]["local_costmap"]["ros__parameters"]["footprint"]
        self.footprint = yaml.safe_load(fp) if isinstance(fp, str) else fp   # [[x, y], ...] m
        self.vehicle: Optional[Tuple[float, float, float]] = None     # x, y (m), yön (rad)
        self.trail: List[Tuple[float, float]] = []
        self.path: List[Tuple[float, float]] = []
        self.scan = np.zeros((0, 2))
        self.markers: List[Marker] = []
        self.setMinimumSize(560, 380)

    @staticmethod
    def _render(classes: np.ndarray) -> QImage:
        """Sınıflar → RGBA görüntü. Engeller 1 piksel kalınlaştırılır: lidarın seyrek
        noktaları düz blok gibi görünsün."""
        occ = classes == ms.OCCUPIED
        thick = occ.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            thick |= np.roll(np.roll(occ, dy, axis=0), dx, axis=1)
        h, w = classes.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        for mask, key in ((classes == ms.UNKNOWN, "outside"), (classes == ms.FREE, "ground"),
                          (thick, "obstacle")):
            c = QColor(th.MAP[key])
            rgba[mask] = (c.red(), c.green(), c.blue(), 255)
        return QImage(rgba.tobytes(), w, h, 4 * w, QImage.Format_RGBA8888).copy()

    # ---- durum (panel çağırır) ----------------------------------------------------

    def set_vehicle(self, x: float, y: float, yaw: float) -> None:
        self.vehicle = (x, y, yaw)
        if not self.trail or math.dist(self.trail[-1], (x, y)) >= TRAIL_STEP_M:
            self.trail = (self.trail + [(x, y)])[-TRAIL_MAX:]

    def add_marker(self, task_id: str, x: float, y: float, label: str, named: bool = False) -> None:
        self.markers = [mk for mk in self.markers if mk.task_id != task_id][-11:]   # son 12 hedef
        self.markers.append(Marker(task_id, x, y, label, named))

    def resolve(self, task_id: str, accepted: bool, hint: Optional[Tuple[float, float]]) -> None:
        for mk in self.markers:
            if mk.task_id == task_id:
                mk.state = "kabul" if accepted else "ret"
                mk.hint = None if accepted else hint
                mk.t = time.monotonic()

    def clear_task(self) -> None:
        """Yeni görev: önceki hedefler, yol ve iz silinir."""
        self.markers, self.path = [], []
        self.trail = self.trail[-1:]

    # ---- koordinat ------------------------------------------------------------------

    def _fit(self) -> None:
        w, h = self.image.width(), self.image.height()
        self.k = min(self.width() / w, self.height() / h)            # ekran pikseli / harita pikseli
        self.ox = (self.width() - w * self.k) / 2
        self.oy = (self.height() - h * self.k) / 2
        self.ppm = self.k / self.res                                  # ekran pikseli / metre

    def to_screen(self, x: float, y: float) -> QPointF:
        px, py = pt.world_to_px(x, y, self.origin, self.res, self.image.height())
        return QPointF(self.ox + px * self.k, self.oy + py * self.k)

    # ---- çizim --------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        self._fit()
        now = time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        try:
            p.fillRect(self.rect(), _qc("outside"))
            p.drawImage(QRectF(self.ox, self.oy, self.image.width() * self.k,
                               self.image.height() * self.k), self.image)
            self._grid(p)
            self._zones(p)
            self._trail(p)
            self._lidar(p)
            self._path(p, now)
            self._markers(p, now)
            self._vehicle(p)
            self._compass(p)
            self._scale(p)
            self._legend(p)
        finally:
            p.end()                             # çizimde hata olsa da çizici kapanır

    def _font(self, size: float, bold: bool = False) -> QFont:
        f = QFont(th.FONT)
        f.setPixelSize(max(9, int(size)))
        f.setBold(bold)
        return f

    def _pill(self, p: QPainter, at: QPointF, text: str, fg: QColor, bg: QColor,
              size: float = 12, bold: bool = True) -> None:
        """Yazıyı yarı saydam, yuvarlak köşeli bir zeminle; at = yazının sol orta noktası."""
        p.setFont(self._font(size, bold))
        r = p.fontMetrics().boundingRect(text)
        box = QRectF(at.x(), at.y() - r.height() / 2 - 3, r.width() + 14, r.height() + 6)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(box, box.height() / 2, box.height() / 2)
        p.setPen(fg)
        p.drawText(box, Qt.AlignCenter, text)

    def _grid(self, p: QPainter) -> None:
        (x0, y0), (x1, y1) = self.origin, (self.origin[0] + self.image.width() * self.res,
                                           self.origin[1] + self.image.height() * self.res)
        p.setPen(QPen(_qc("grid"), 1))
        x = math.ceil(x0 / GRID_M) * GRID_M
        while x <= x1:
            p.drawLine(self.to_screen(x, y0), self.to_screen(x, y1))
            x += GRID_M
        y = math.ceil(y0 / GRID_M) * GRID_M
        while y <= y1:
            p.drawLine(self.to_screen(x0, y), self.to_screen(x1, y))
            y += GRID_M

    def _zones(self, p: QPainter) -> None:
        # izinli alanın sınırı: bariyer (amber, kesik)
        pen = QPen(_qc("barrier", 0.85), 2.5, Qt.CustomDashLine)
        pen.setDashPattern([6, 4])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF([self.to_screen(*c) for c in self.site["allowed"]]))
        # yasak bölgeler: yarı saydam dolgu + çapraz tarama + kalın kenar + ad rozeti
        for name, poly in self.site["forbidden"].items():
            pts = QPolygonF([self.to_screen(*c) for c in poly])
            p.setPen(Qt.NoPen)
            p.setBrush(_qc("forbidden", 0.16))
            p.drawPolygon(pts)
            p.setBrush(QBrush(_qc("forbidden", 0.45), Qt.BDiagPattern))
            p.drawPolygon(pts)
            p.setPen(QPen(_qc("forbidden", 0.95), 2))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(pts)
            box = pts.boundingRect()                 # ad üst kenarda: orta, ret işaretine kalır
            label = f"⛔ {name.upper()}"
            p.setFont(self._font(12, True))
            tw = p.fontMetrics().horizontalAdvance(label) + 14
            self._pill(p, QPointF(box.center().x() - tw / 2, box.top()), label, QColor("white"),
                       _qc("forbidden", 0.85))
        for name, (x, y) in self.site["safe_points"].items():
            at = self.to_screen(x, y)
            p.setPen(QPen(_qc("safe"), 2.5))
            p.setBrush(_qc("safe", 0.18))
            p.drawEllipse(at, 9, 9)
            p.setPen(Qt.NoPen)
            p.setBrush(_qc("safe"))
            p.drawEllipse(at, 3.5, 3.5)
            self._pill(p, at + QPointF(12, 0), name, _qc("safe"), _qc("outside", 0.7), 11)
        for name, xyd in self.site.get("places", {}).items():     # [x, y, varış yönü (derece)]
            at = self.to_screen(xyd[0], xyd[1])
            p.setPen(QPen(_qc("place"), 1.5))
            p.setBrush(_qc("place", 0.35))
            p.drawEllipse(at, 5, 5)
            self._pill(p, at + QPointF(8, 0), name, _qc("place"), _qc("outside", 0.6), 11, False)

    def _trail(self, p: QPainter) -> None:
        n = len(self.trail)
        if n < 2:
            return
        chunk = 15                                   # eski kısımlar soluk, yeniler parlak
        for i in range(0, n - 1, chunk):
            seg = self.trail[i:i + chunk + 1]
            alpha = min(0.85, 0.15 + 0.7 * (i + chunk) / n)
            p.setPen(QPen(_qc("trail", alpha), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline(QPolygonF([self.to_screen(x, y) for x, y in seg]))

    def _lidar(self, p: QPainter) -> None:
        if not len(self.scan):
            return
        p.setPen(Qt.NoPen)
        p.setBrush(_qc("lidar", 0.85))
        for x, y in self.scan:
            p.drawEllipse(self.to_screen(x, y), 1.8, 1.8)

    def _path(self, p: QPainter, now: float) -> None:
        if len(self.path) < 2:
            return
        poly = QPolygonF([self.to_screen(x, y) for x, y in self.path])
        p.setPen(QPen(_qc("path", 0.25), 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))   # parıltı
        p.drawPolyline(poly)
        pen = QPen(_qc("path"), 3, Qt.CustomDashLine, Qt.RoundCap, Qt.RoundJoin)
        pen.setDashPattern([3, 2.5])
        pen.setDashOffset(-(now * 6) % 5.5)          # çizgi hedefe doğru akar
        p.setPen(pen)
        p.drawPolyline(poly)

    def _ring(self, p: QPainter, at: QPointF, color: str, phase: Optional[Tuple[float, float]],
              r0: float, r1: float) -> None:
        if phase is None:
            return
        size, alpha = phase
        p.setPen(QPen(_qc(color, 0.95 * alpha), 4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(at, r0 + (r1 - r0) * size, r0 + (r1 - r0) * size)

    def _arrow(self, p: QPainter, a: QPointF, b: QPointF, color: QColor) -> None:
        pen = QPen(color, 2.5, Qt.CustomDashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawLine(a, b)
        ang = math.atan2(b.y() - a.y(), b.x() - a.x())
        head = [b, b - QPointF(14 * math.cos(ang - 0.4), 14 * math.sin(ang - 0.4)),
                b - QPointF(14 * math.cos(ang + 0.4), 14 * math.sin(ang + 0.4))]
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPolygon(QPolygonF(head))

    def _markers(self, p: QPainter, now: float) -> None:
        last_ok = next((mk for mk in reversed(self.markers) if mk.state == "kabul"), None)
        for mk in self.markers:
            at = self.to_screen(mk.x, mk.y)
            age = now - mk.t
            if mk.state == "ret":
                if mk.hint is not None:
                    self._arrow(p, at, self.to_screen(*mk.hint), _qc("safe", 0.9))
                if age < REJECT_PULSE_S * REJECT_PULSES:
                    self._ring(p, at, "forbidden", pt.ring(age % REJECT_PULSE_S, REJECT_PULSE_S), 10, 46)
                p.setPen(Qt.NoPen)
                p.setBrush(_qc("forbidden", 0.25))
                p.drawEllipse(at, 16, 16)
                p.setPen(QPen(_qc("forbidden"), 5, Qt.SolidLine, Qt.RoundCap))
                d = 10
                p.drawLine(at + QPointF(-d, -d), at + QPointF(d, d))
                p.drawLine(at + QPointF(-d, d), at + QPointF(d, -d))
                self._pill(p, at + QPointF(18, -24), f"RET · {mk.label}", QColor("white"),
                           _qc("forbidden", 0.95), 12)
            else:
                ok = mk.state == "kabul"
                color = "safe" if ok else "muted"
                if ok and mk is last_ok:                       # etkin hedef nabız atar
                    self._ring(p, at, "safe", pt.ring(now % 1.6, 1.6), 8, 30)
                p.setPen(QPen(_qc(color), 3, Qt.SolidLine, Qt.RoundCap))
                top = at + QPointF(0, -26)
                p.drawLine(at, top)                           # bayrak direği
                p.setPen(Qt.NoPen)
                p.setBrush(_qc(color))
                p.drawPolygon(QPolygonF([top, top + QPointF(18, 6), top + QPointF(0, 12)]))
                p.drawEllipse(at, 3, 3)
                if not mk.named:                              # adlı yerin etiketi haritada var
                    self._pill(p, top + QPointF(22, 6), mk.label,
                               QColor("#04101f") if ok else QColor("white"), _qc(color, 0.9), 12)

    def _vehicle(self, p: QPainter) -> None:
        if self.vehicle is None:
            return
        x, y, yaw = self.vehicle
        at = self.to_screen(x, y)
        s = self.ppm
        p.save()
        p.translate(at)
        p.rotate(-math.degrees(yaw))            # ekranda y aşağı: açı ters yönde
        front = max(fx for fx, _ in self.footprint)
        # far ışığı: önde yarı saydam koni
        cone = QPainterPath(QPointF(front * s, 0))
        cone.arcTo(QRectF((front - 3.5) * s, -3.5 * s, 7 * s, 7 * s), 25, -50)
        cone.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(_qc("headlight", 0.18))
        p.drawPath(cone)
        body = QPolygonF([QPointF(fx * s, -fy * s) for fx, fy in self.footprint])
        p.setPen(QPen(_qc("outside"), 2))
        p.setBrush(_qc("vehicle"))
        p.drawPolygon(body)
        p.setPen(Qt.NoPen)
        p.setBrush(_qc("accent"))                # ön tampon şeridi: yön hemen okunsun
        r = body.boundingRect()
        p.drawRect(QRectF(r.right() - 0.18 * s, r.top() + 0.08 * s, 0.14 * s, r.height() - 0.16 * s))
        p.restore()

    def _compass(self, p: QPainter) -> None:
        c = QPointF(self.width() - 34, 38)
        p.setPen(Qt.NoPen)
        p.setBrush(_qc("outside", 0.75))
        p.drawEllipse(c, 22, 22)
        p.setBrush(_qc("forbidden"))
        p.drawPolygon(QPolygonF([c + QPointF(0, -16), c + QPointF(6, 2), c + QPointF(-6, 2)]))
        p.setBrush(_qc("muted"))
        p.drawPolygon(QPolygonF([c + QPointF(0, 16), c + QPointF(6, 2), c + QPointF(-6, 2)]))
        p.setPen(QColor(th.C["text"]))
        p.setFont(self._font(11, True))
        p.drawText(QRectF(c.x() - 10, c.y() - 42, 20, 16), Qt.AlignCenter, "K")

    def _scale(self, p: QPainter) -> None:
        length = GRID_M * self.ppm
        right, bottom = self.width() - 24, self.height() - 22
        a, b = QPointF(right - length, bottom), QPointF(right, bottom)
        p.setPen(QPen(QColor(th.C["text"]), 2))
        p.drawLine(a, b)
        p.drawLine(a, a + QPointF(0, -6))
        p.drawLine(b, b + QPointF(0, -6))
        p.setFont(self._font(11, True))
        p.drawText(QRectF(a.x(), bottom - 22, length, 16), Qt.AlignCenter, f"{pt.num(GRID_M)} m")

    def _legend(self, p: QPainter) -> None:
        items = [("vehicle", "araç", "box"), ("path", "Nav2 yolu", "line"), ("trail", "geçilen iz", "line"),
                 ("lidar", "lidar", "dot"), ("forbidden", "yasak bölge", "box"),
                 ("safe", "güvenli nokta", "ring"), ("place", "yer adı", "dot"),
                 ("barrier", "saha sınırı", "line")]
        p.setFont(self._font(11))
        row = 18
        box = QRectF(14, self.height() - 14 - row * len(items) - 12, 130, row * len(items) + 12)
        p.setPen(QPen(_qc("border"), 1))
        p.setBrush(_qc("outside", 0.8))
        p.drawRoundedRect(box, 8, 8)
        for i, (key, label, shape) in enumerate(items):
            y = box.top() + 6 + row * i + row / 2
            sym = QPointF(box.left() + 16, y)
            p.setBrush(Qt.NoBrush)
            if shape == "line":
                p.setPen(QPen(_qc(key), 3))
                p.drawLine(sym + QPointF(-8, 0), sym + QPointF(8, 0))
            elif shape == "ring":
                p.setPen(QPen(_qc(key), 2))
                p.drawEllipse(sym, 5, 5)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(_qc(key, 0.9))
                if shape == "box":
                    p.drawRect(QRectF(sym.x() - 7, y - 5, 14, 10))
                else:
                    p.drawEllipse(sym, 3.5, 3.5)
            p.setPen(QColor(th.C["text"]))
            p.drawText(QRectF(box.left() + 32, y - row / 2, 100, row), Qt.AlignVCenter, label)
