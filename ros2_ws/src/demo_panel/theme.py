"""Demo panelinin görünümü: renkler ve Qt stil sayfası tek yerde (koyu "kontrol merkezi").

Renk adları anlamlarıyla: durum renkleri (green/amber/red/muted) rozet, ışık ve balonlarda
aynıdır; harita katmanlarının renkleri MAP'te. Başka dosya renk kodu yazmaz.
"""
from __future__ import annotations

C = {
    "bg": "#0a0f1c",          # pencere zemini
    "panel": "#0f1729",       # üst şerit
    "card": "#131d33",        # kartlar
    "card_hi": "#1a2742",     # kart başlığı, giriş kutusu
    "border": "#243352",
    "text": "#e6edf7",
    "muted": "#7f8db0",
    "accent": "#3ea6ff",
    "cyan": "#22d3ee",
    "green": "#22c55e",
    "amber": "#f59e0b",
    "red": "#ef4444",
}

MAP = {
    "outside": "#070b15",     # haritanın bilinmeyen kısmı
    "ground": "#1b2335",      # boş zemin (asfalt)
    "obstacle": "#56647f",    # engel (konteyner, bariyer, tank)
    "grid": "#26324d",
    "barrier": "#f59e0b",     # izinli alanın sınırı (bariyer çizgisi)
    "forbidden": "#ef4444",
    "safe": "#22c55e",
    "place": "#7fb4ff",
    "path": "#3ea6ff",
    "trail": "#a78bfa",
    "lidar": "#22d3ee",
    "vehicle": "#e6edf7",
    "headlight": "#fde68a",
}

# Konuşma balonu türü → (zemin, kenar, başlık rengi, sağa yaslı mı)
BUBBLE = {
    "gorev": ("#1e3a8a", "#3b82f6", "#bfdbfe", True),
    "komut": ("#16213a", "#2b3a5c", "#93c5fd", False),
    "kabul": ("#0d2a1c", "#22c55e", "#86efac", False),
    "ret": ("#33121a", "#ef4444", "#fca5a5", False),
    "gecersiz": ("#33240b", "#f59e0b", "#fcd34d", False),
    "uyari": ("#33240b", "#f59e0b", "#fcd34d", False),
    "son": ("#221a3d", "#a78bfa", "#ddd6fe", False),
    "panel": ("#131d33", "#243352", "#7f8db0", False),
}
BUBBLE_ICON = {"gorev": "👤", "komut": "🤖", "kabul": "🛡️", "ret": "🛡️", "gecersiz": "⚠️",
               "uyari": "⚠️", "son": "🏁", "panel": "ℹ️"}

FONT = "Ubuntu"

QSS = f"""
QMainWindow, QWidget#root {{ background: {C['bg']}; }}
QWidget {{ color: {C['text']}; font-family: {FONT}; font-size: 13px; }}
QFrame#header {{ background: {C['panel']}; border-bottom: 1px solid {C['border']}; }}
QLabel#title {{ font-size: 20px; font-weight: 700; letter-spacing: 1px; }}
QLabel#subtitle {{ color: {C['muted']}; font-size: 12px; }}
QLabel#chip {{ background: {C['card_hi']}; border: 1px solid {C['accent']}; color: {C['accent']};
              border-radius: 11px; padding: 3px 12px; font-weight: 600; }}
QLabel#clock {{ font-family: "Ubuntu Mono"; font-size: 18px; color: {C['text']}; }}
QFrame#card {{ background: {C['card']}; border: 1px solid {C['border']}; border-radius: 12px; }}
QLabel#cardTitle {{ color: {C['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
QLabel#value {{ font-size: 15px; }}
QLabel#hint {{ color: {C['muted']}; font-size: 12px; }}
QLineEdit {{ background: {C['card_hi']}; border: 1px solid {C['border']}; border-radius: 10px;
             padding: 10px 14px; font-size: 15px; selection-background-color: {C['accent']}; }}
QLineEdit:focus {{ border: 1px solid {C['accent']}; }}
QPushButton {{ background: {C['card_hi']}; border: 1px solid {C['border']}; border-radius: 10px;
               padding: 10px 20px; font-size: 14px; font-weight: 600; }}
QPushButton:hover {{ border: 1px solid {C['accent']}; }}
QPushButton#primary {{ background: {C['accent']}; border: none; color: #04101f; }}
QPushButton#primary:hover {{ background: #6cbcff; }}
QPushButton#danger {{ color: {C['amber']}; border: 1px solid {C['amber']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QSplitter::handle {{ background: {C['bg']}; }}
QToolTip {{ background: {C['card_hi']}; color: {C['text']}; border: 1px solid {C['border']}; }}
"""
