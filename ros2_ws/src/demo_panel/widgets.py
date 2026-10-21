"""Demo panelinin parçaları (Qt): kart çerçevesi, sistem ışığı, hız göstergesi, durum rozeti,
konuşma balonları. Renkler theme.py'den; metinler panel_text.py'den gelir."""
from __future__ import annotations

import math
import time
from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

import panel_text as pt
import theme as th


class Card(QFrame):
    """Başlıklı, yuvarlak köşeli kutu. İçerik self.body'ye eklenir."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)
        head = QLabel(title.upper())
        head.setObjectName("cardTitle")
        lay.addWidget(head)
        self.body = lay


class Light(QWidget):
    """Üst şeritte parlayan nokta + ad: ok yeşil, stale kırmızı, none gri."""

    COLOR = {"ok": "green", "stale": "red", "none": "muted"}

    def __init__(self, name: str, parent=None) -> None:
        super().__init__(parent)
        self.name, self.state = name, "none"
        self.setFixedSize(84, 28)
        self.setToolTip(f"{name}: canlı mı")

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(th.C[self.COLOR[self.state]])
        center = QPointF(12, 14)
        if self.state == "ok":                       # hafif nabız: canlı olduğu görülsün
            glow = 0.35 + 0.25 * math.sin(time.monotonic() * 3)
            g = QRadialGradient(center, 11)
            halo = QColor(c)
            halo.setAlphaF(glow)
            g.setColorAt(0, halo)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(center, 11, 11)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(center, 5, 5)
        p.setPen(QColor(th.C["text"] if self.state == "ok" else th.C["muted"]))
        f = QFont(th.FONT)
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(24, 0, 60, 28), Qt.AlignVCenter | Qt.AlignLeft, self.name)
        p.end()


class Gauge(QWidget):
    """Yay biçimli hız göstergesi: 0'dan vmax'a; kartın sınırı (limit) kırmızı çizgi.
    Sınıra yaklaştıkça renk yeşil → amber → kırmızı."""

    SWEEP = 240                                    # derece; 0 sol altta, en büyük sağ altta

    def __init__(self, limit: Optional[float], parent=None) -> None:
        super().__init__(parent)
        self.limit = limit
        self.vmax = (limit or 0.6) * 1.25
        self.v = 0.0
        self.setMinimumSize(170, 130)

    def set_value(self, v: float) -> None:
        self.v = v
        self.update()

    def _angle(self, frac: float) -> float:          # Qt açısı: 0 = doğu, saat yönü tersine
        return 90 + self.SWEEP / 2 - frac * self.SWEEP

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height() * 1.25) - 16
        rect = QRectF((self.width() - side) / 2, 10, side, side)
        start = int(self._angle(0) * 16)
        p.setPen(QPen(QColor(th.C["border"]), 12, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, start, int(-self.SWEEP * 16))
        frac = pt.gauge_fraction(self.v, self.vmax)
        ratio = abs(self.v) / self.limit if self.limit else 0
        color = th.C["red"] if ratio > 1 else th.C["amber"] if ratio > 0.85 else th.C["green"]
        if frac > 0:
            p.setPen(QPen(QColor(color), 12, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, start, int(-self.SWEEP * frac * 16))
        if self.limit:                               # kartın sınırı
            a = math.radians(self._angle(self.limit / self.vmax))
            c, r = rect.center(), side / 2
            p.setPen(QPen(QColor(th.C["red"]), 3))
            p.drawLine(QPointF(c.x() + (r - 12) * math.cos(a), c.y() - (r - 12) * math.sin(a)),
                       QPointF(c.x() + (r + 8) * math.cos(a), c.y() - (r + 8) * math.sin(a)))
        p.setPen(QColor(th.C["text"]))
        f = QFont(th.FONT)
        f.setPointSize(22)
        f.setBold(True)
        p.setFont(f)
        p.drawText(rect.adjusted(0, -8, 0, -8), Qt.AlignCenter, pt.num(abs(self.v), 2))
        f.setPointSize(10)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(th.C["muted"]))
        unit = "m/s" + (f" · sınır {pt.num(self.limit, 2)}" if self.limit else "")
        p.drawText(rect.adjusted(0, 34, 0, 34), Qt.AlignCenter, unit)
        p.end()


class StateBadge(QWidget):
    """Kartın durumu: büyük renkli rozet; HOLD ve BAĞLANTI YOK'ta kenar nabız atar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.color_key, self.text = "muted", "KART YOK"
        self.setMinimumHeight(64)

    def set_state(self, color_key: str, text: str) -> None:
        self.color_key, self.text = color_key, text
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(th.C[self.color_key])
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        fill = QColor(c)
        fill.setAlphaF(0.18)
        p.setBrush(fill)
        width = 2.0
        if self.text in ("HOLD", "BAĞLANTI YOK"):
            width = 2 + 2.5 * (0.5 + 0.5 * math.sin(time.monotonic() * 5))
        p.setPen(QPen(c, width))
        p.drawRoundedRect(r, 12, 12)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(r.left() + 26, r.center().y()), 8, 8)
        p.setPen(c.lighter(130))
        f = QFont(th.FONT)
        f.setPointSize(20)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r.adjusted(48, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text)
        p.end()


class ChatView(QScrollArea):
    """Mesajlaşma uygulaması gibi balonlar: operatör sağda, ajan ve kart solda."""

    MAX = 150

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(2, 2, 6, 2)
        self.lay.setSpacing(8)
        self.lay.addStretch(1)
        self.setWidget(inner)
        self.verticalScrollBar().rangeChanged.connect(
            lambda _lo, hi: self.verticalScrollBar().setValue(hi))   # hep en yeni balon görünür

    def separator(self, text: str) -> None:
        lab = QLabel(f"──────  {text}  ──────")
        lab.setAlignment(Qt.AlignCenter)
        lab.setStyleSheet(f"color: {th.C['muted']}; font-size: 11px; padding: 6px 0;")
        self._insert(lab)

    def add(self, kind: str, title: str, body: str) -> None:
        bg, edge, head, right = th.BUBBLE.get(kind, th.BUBBLE["panel"])
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {bg}; border: 1px solid {edge}; "
                            f"border-radius: 12px; }} QLabel {{ border: none; background: transparent; }}")
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 8, 12, 10)
        v.setSpacing(3)
        top = QLabel(f"{th.BUBBLE_ICON.get(kind, '')}  <b>{title}</b>"
                     f"<span style='color:{th.C['muted']}'>  ·  {time.strftime('%H:%M:%S')}</span>")
        top.setStyleSheet(f"color: {head}; font-size: 12px;")
        v.addWidget(top)
        if body:
            text = QLabel(body)
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            text.setStyleSheet(f"color: {th.C['text']}; font-size: 14px;")
            v.addWidget(text)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if right:
            row.addStretch(1)
        row.addWidget(frame, 6)
        if not right:
            row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        self._insert(holder)

    def _insert(self, w: QWidget) -> None:
        self.lay.insertWidget(self.lay.count() - 1, w)     # esnek boşluğun önüne
        while self.lay.count() - 1 > self.MAX:
            old = self.lay.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
