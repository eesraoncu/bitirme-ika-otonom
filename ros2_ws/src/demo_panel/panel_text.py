"""Demo panelinin metinleri, durumları ve küçük hesapları (Faz 6, demo, K-071).

ROS'a ve Qt'ye bağlı değildir: düz sözlük/sayı alır, düz metin/sayı döndürür,
PC'de pytest ile sınanır (tests/test_panel_text.py). Panel (demo_panel.py) bu
fonksiyonları ROS mesajlarının JSON'una uygular.

Kaynak konular: /guard/task ve /guard/feedback (K-050), /guard/verdict (köprü,
convert.verdict_text), /guard/status (STATUS, K-060), /agent/log (agent_core olayları).
Ondalık virgül ve "(x; y)" m, kartın gerekçe metinleriyle aynı (protocol §7.3).
Konuşma balonu: (tür, başlık, gövde); tür rengi seçer (theme.BUBBLE).
"""
from __future__ import annotations

import re
from typing import Optional, Sequence, Tuple

STATUS_STALE_S = 2.5     # STATUS saniyede bir gelir: 2,5 s gelmezse kartla bağlantı yok sayılır
LIVE_STALE_S = 2.0       # sim (odom) için aynı ölçüt

CONFIG_NAME = {"A": "bekçi yok", "B": "yalnız Nav2", "C": "kart, gerekçesiz", "D": "kart, gerekçeli"}

# Kart rozeti: durum → (renk anahtarı, metin). Renkler theme.py'de.
BADGE = {
    "NORMAL": ("green", "NORMAL"),
    "RECOVERY": ("amber", "KURTARMA"),
    "HOLD": ("red", "HOLD"),
    "stale": ("muted", "BAĞLANTI YOK"),
    "none": ("muted", "KART YOK"),
}
BADGE_HINT = {
    "NORMAL": "komutlar denetleniyor",
    "KURTARMA": "araç güvenli noktaya götürülüyor",
    "HOLD": "araç duruyor · SIFIRLA bekleniyor",
    "BAĞLANTI YOK": "karttan 2,5 s'dir haber yok",
    "KART YOK": "bu yapılandırmada kart yok",
}

Bubble = Tuple[str, str, str]
Box = Tuple[float, float, float, float]          # x0, y0, x1, y1 (ekran pikseli)
Points = Sequence[Tuple[float, float]]


def num(v: float, nd: int = 1) -> str:
    """Ondalık virgüllü sayı; gereksiz sıfırlar atılır: 14.5 → '14,5', 10.0 → '10'."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return ("0" if s in ("", "-0") else s).replace(".", ",")


def point(x: float, y: float) -> str:
    return f"({num(x)}; {num(y)})"


def config_label(config: str) -> str:
    return f"{config} · {CONFIG_NAME[config]}" if config in CONFIG_NAME else ""


def task_line(task: dict) -> str:
    """/guard/task JSON'u → komutun okunur hâli."""
    cmd = task.get("cmd")
    if cmd == "git":
        where = point(task.get("x", 0.0), task.get("y", 0.0))
        yer = task.get("yer")
        return f"git → {yer} {where}" if yer else f"git → {where}"
    if cmd == "bekle":
        return f"bekle {num(task.get('sure_s', 0.0))} s"
    if cmd == "hiz_siniri":
        return f"hız sınırı {num(task.get('deger_mps', 0.0), 2)} m/s"
    if cmd == "dur":
        return "dur"
    return f"bilinmeyen komut: {cmd}"


def task_bubble(task: dict) -> Bubble:
    return "komut", "Ajan → kart", task_line(task)


def feedback_bubble(fb: dict, verdict: Optional[dict] = None) -> Bubble:
    """/guard/feedback (+ eşleşen ret kararı) → balon. verdict yalnız ret kararıysa verilir;
    C'de ajan gerekçeyi görmez ama izleyici kuralı başlıkta görür."""
    text = fb.get("text", "")
    if fb.get("accepted"):
        return "kabul", "Kart · KABUL", text
    rule = f" · {verdict['rule']}" if verdict and verdict.get("rule") else ""
    return "ret", f"Kart · RET{rule}", text


def is_rejection(verdict: dict) -> bool:
    return verdict.get("result") not in (None, "ACCEPTED")


def log_bubble(event: dict) -> Optional[Bubble]:
    """/agent/log olayı → balon ya da None (panelde gösterilmeyen olay).
    'adım' yalnız karta gitmeyen (geçersiz) çağrıda gösterilir: karta giden komut zaten
    /guard/task ve /guard/feedback'ten canlı geliyor (adım olayı Nav2 vardıktan sonra yazılır)."""
    kind = event.get("event")
    if kind == "görev":
        return "gorev", "Operatör", event.get("text", "")
    if kind == "adım" and event.get("task") is None:
        return "gecersiz", f"Ajan · geçersiz çağrı ({event.get('tool', '?')})", event.get("result", "")
    if kind == "bitti":
        return "son", "Ajan · bitti", event.get("summary", "")
    if kind == "vazgeçti":
        return "son", "Ajan · vazgeçti", f"{event.get('rejections', '?')} ret sonra görev bırakıldı."
    if kind == "adım sınırı":
        return "son", "Ajan · adım sınırı", f"{event.get('steps', '?')} adımda bitirilemedi."
    if kind == "meşgul":
        return "uyari", "Ajan · meşgul", f"Görev alınmadı: “{event.get('text', '')}”"
    if kind == "hata":
        return "uyari", "Ajan · hata", event.get("error", "")
    return None


def badge(status: Optional[dict], age_s: Optional[float]) -> Tuple[str, str]:
    """Kart rozeti → (renk anahtarı, metin). status None: kart hiç görülmedi (A/B ya da köprü yok)."""
    if status is None:
        return BADGE["none"]
    if age_s is None or age_s > STATUS_STALE_S:
        return BADGE["stale"]
    return BADGE.get(status.get("state"), ("muted", str(status.get("state"))))


def light(age_s: Optional[float], stale_s: float = LIVE_STALE_S) -> str:
    """Üst şeritteki ışık: 'none' (hiç gelmedi), 'ok' (canlı), 'stale' (kesildi)."""
    if age_s is None:
        return "none"
    return "ok" if age_s <= stale_s else "stale"


def ring(t: float, duration: float) -> Optional[Tuple[float, float]]:
    """Yayılan halka animasyonu: olaydan t s sonra (büyüklük 0→1, saydamlık 1→0); bitince None."""
    if t < 0 or t > duration:
        return None
    f = t / duration
    return f, 1.0 - f


def gauge_fraction(v: float, vmax: float) -> float:
    """Hız göstergesinin dolu oranı (0–1); geri gitme de büyüklüğüyle gösterilir."""
    return 0.0 if vmax <= 0 else min(1.0, abs(v) / vmax)


def clock(seconds: float) -> str:
    """Simülasyon saati: 134,7 → '02:14'."""
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def speed_limit_from_header(text: str) -> Optional[float]:
    """Kartın hız sınırı (m/s), firmware/app/rules/limits/limits.h'deki LIMIT_V_MAX_MM_S'ten
    (tek kaynak; RULES §1). Bulunamazsa None: gösterge sınır çizgisiz çizilir."""
    m = re.search(r"#define\s+LIMIT_V_MAX_MM_S\s+(\d+)", text)
    return int(m.group(1)) / 1000 if m else None


def world_to_px(x: float, y: float, origin: Tuple[float, float], resolution: float,
                height_px: int) -> Tuple[float, float]:
    """Harita çerçevesi (m) → harita görüntüsünün pikseli. Nav2 haritasında origin sol ALT
    köşedir, görüntünün ilk satırı ise ÜST kenar: y ekseni ters çevrilir."""
    return (x - origin[0]) / resolution, height_px - (y - origin[1]) / resolution


def _overlap(a: Points, b: Points) -> bool:
    """İki dışbükey çokgen üst üste biniyor mu (ayırıcı eksen yöntemi): herhangi bir kenarın
    normali üzerine izdüşümleri ayrıksa bir ayırıcı eksen var, çakışma yok. Değmek çakışmadır."""
    for poly in (a, b):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y1 - y2, x2 - x1                       # kenarın normali
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def label_side(candidates: Sequence[Tuple[str, Box]], body: Optional[Points]) -> str:
    """Etiketin yeri: adaylardan (sırayla) aracın gövdesiyle çakışmayan ilki. Gövde yoksa ya da
    hepsi çakışıyorsa ilk aday. Gövde: aracın izi, ekran pikselinde, döndürülmüş (dışbükey)."""
    if body:
        for side, (x0, y0, x1, y1) in candidates:
            if not _overlap([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], body):
                return side
    return candidates[0][0]
