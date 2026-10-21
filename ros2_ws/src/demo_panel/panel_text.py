"""Demo panelinin metinleri ve harita dönüşümü (Faz 6, demo).

ROS'a ve Qt'ye bağlı değildir: düz sözlük/sayı alır, düz metin/sayı döndürür,
PC'de pytest ile sınanır (tests/test_panel_text.py). Panel (demo_panel.py) bu
fonksiyonları ROS mesajlarının JSON'una uygular.

Kaynak konular: /guard/task ve /guard/feedback (K-050), /guard/verdict (köprü,
convert.verdict_text), /guard/status (STATUS, K-060), /agent/log (agent_core olayları).
Ondalık virgül ve "(x; y)" m, kartın gerekçe metinleriyle aynı (protocol §7.3).
"""
from __future__ import annotations

from typing import Optional, Tuple

STATUS_STALE_S = 2.5     # STATUS saniyede bir gelir: 2,5 s gelmezse kartla bağlantı yok sayılır

# Rozet renkleri: kartın durumu (NORMAL / RECOVERY / HOLD), bağlantı yok, kart hiç görülmedi
BADGE = {
    "NORMAL": ("#1f9d55", "NORMAL"),
    "RECOVERY": ("#e07b00", "KURTARMA"),
    "HOLD": ("#c62828", "HOLD (beklemede)"),
    "stale": ("#6b6b6b", "BAĞLANTI YOK"),
    "none": ("#6b6b6b", "KART YOK"),
}


def num(v: float, nd: int = 1) -> str:
    """Ondalık virgüllü sayı; gereksiz sıfırlar atılır: 14.5 → '14,5', 10.0 → '10'."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return ("0" if s in ("", "-0") else s).replace(".", ",")


def point(x: float, y: float) -> str:
    return f"({num(x)}; {num(y)})"


def task_line(task: dict) -> str:
    """/guard/task JSON'u → 'Ajan → kart' satırı."""
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


def feedback_line(fb: dict, verdict: Optional[dict] = None) -> Tuple[str, str]:
    """/guard/feedback (+ eşleşen ret kararı) → (satır, tür). Tür: 'kabul' ya da 'ret'.
    verdict yalnız ret kararıysa verilir; C'de ajan gerekçeyi görmez ama izleyici kuralı görür."""
    text = fb.get("text", "")
    if fb.get("accepted"):
        return "✓ KABUL", "kabul"
    rule = f" · {verdict['rule']}" if verdict and verdict.get("rule") else ""
    return f"✗ RET{rule} — {text}", "ret"


def is_rejection(verdict: dict) -> bool:
    return verdict.get("result") not in (None, "ACCEPTED")


def log_line(event: dict) -> Optional[Tuple[str, str]]:
    """/agent/log olayı → (satır, tür) ya da None (panelde gösterilmeyen olay).
    'adım' yalnız karta gitmeyen (geçersiz) çağrıda gösterilir: karta giden komut zaten
    /guard/task ve /guard/feedback'ten canlı geliyor (adım olayı Nav2 vardıktan sonra yazılır)."""
    kind = event.get("event")
    if kind == "görev":
        return f"Görev: “{event.get('text', '')}”", "gorev"
    if kind == "adım" and event.get("task") is None:
        return f"Geçersiz çağrı ({event.get('tool', '?')}) — {event.get('result', '')}", "gecersiz"
    if kind == "bitti":
        return f"Ajan bitirdi: {event.get('summary', '')}", "son"
    if kind == "vazgeçti":
        return f"Ajan vazgeçti ({event.get('rejections', '?')} ret)", "son"
    if kind == "adım sınırı":
        return f"Ajan adım sınırına ulaştı ({event.get('steps', '?')} adım)", "son"
    if kind == "meşgul":
        return f"Ajan meşgul, görev alınmadı: “{event.get('text', '')}”", "uyari"
    if kind == "hata":
        return f"Ajan hatası: {event.get('error', '')}", "uyari"
    return None


def badge(status: Optional[dict], age_s: Optional[float]) -> Tuple[str, str]:
    """Kart rozeti → (renk, metin). status None: kart hiç görülmedi (A/B ya da köprü yok)."""
    if status is None:
        return BADGE["none"]
    if age_s is None or age_s > STATUS_STALE_S:
        return BADGE["stale"]
    return BADGE.get(status.get("state"), ("#6b6b6b", str(status.get("state"))))


def world_to_px(x: float, y: float, origin: Tuple[float, float], resolution: float,
                height_px: int) -> Tuple[float, float]:
    """Harita çerçevesi (m) → harita görüntüsünün pikseli. Nav2 haritasında origin sol ALT
    köşedir, görüntünün ilk satırı ise ÜST kenar: y ekseni ters çevrilir."""
    return (x - origin[0]) / resolution, height_px - (y - origin[1]) / resolution
