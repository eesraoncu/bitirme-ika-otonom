"""ROS ile protokol arasındaki birim çevirileri (K-040).

ROS metre, radyan ve dördey (quaternion) kullanır; protokol tamsayı cm, mm/s,
mrad (docs/protocol.md §3). Bu modül ROS'a bağlı değildir: düz sayılar alır,
düz sayılar döndürür, PC'de pytest ile sınanır (tests/test_convert.py).

Her alan int16'dır. Sınırın dışı kırpılır: bu taşmayı önlemek içindir, bekçinin
hız sınırı değildir (o kartta, RULES §3.2). NaN ve sonsuz sıfıra çevrilir:
tamsayıda karşılıkları yok, sıfır her alan için güvenli olandır (dur, orijin).
"""
from __future__ import annotations

import json
import math
from typing import Tuple

INT16_MIN, INT16_MAX = -32768, 32767


def to_int16(value: float, scale: float) -> int:
    """value × scale, en yakın tamsayıya yuvarlanmış ve int16'ya kırpılmış."""
    if not math.isfinite(value):
        return 0
    return max(INT16_MIN, min(INT16_MAX, round(value * scale)))


def wrap_angle(a: float) -> float:
    """Açıyı [−π, π) aralığına getirir."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def yaw_from_quaternion(qx: float, qy: float, qz: float, qw: float) -> float:
    """Dördeyden düzlemdeki yön açısı (z ekseni etrafında dönüş), radyan."""
    return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def pose_to_cm(x_m: float, y_m: float, qx: float, qy: float, qz: float, qw: float
               ) -> Tuple[int, int, int]:
    """Harita çerçevesindeki konum → (x_cm, y_cm, yaw_mrad). GOTO_CMD, TELEMETRY."""
    yaw = wrap_angle(yaw_from_quaternion(qx, qy, qz, qw))
    return to_int16(x_m, 100), to_int16(y_m, 100), to_int16(yaw, 1000)


def cm_to_pose(x_cm: int, y_cm: int, yaw_mrad: int) -> Tuple[float, float, float, float]:
    """GOAL → (x_m, y_m, qz, qw). Düzlemde dönüş: qx = qy = 0."""
    half = yaw_mrad / 1000 / 2
    return x_cm / 100, y_cm / 100, math.sin(half), math.cos(half)


def twist_to_cmd(v_m_s: float, w_rad_s: float) -> Tuple[int, int]:
    """Nav2'nin hız komutu → (v_mm_s, w_mrad_s). VELOCITY_CMD."""
    return to_int16(v_m_s, 1000), to_int16(w_rad_s, 1000)


def cmd_to_twist(v_mm_s: int, w_mrad_s: int) -> Tuple[float, float]:
    """DRIVE → (v_m_s, w_rad_s)."""
    return v_mm_s / 1000, w_mrad_s / 1000


def verdict_text(ref_seq: int, result: str, rule: str, reason: str, value: int,
                 lo: int, hi: int, hint_x_cm: int, hint_y_cm: int) -> str:
    """VERDICT → /guard/verdict'e yazılan JSON. Adlar sayı değil metin: ajan okur.
    Gerekçe gizleme (C yapılandırması, protocol §7.3) burada değil, Faz 5'te."""
    return json.dumps({
        "ref_seq": ref_seq, "result": result, "rule": rule, "reason": reason,
        "value": value, "lo": lo, "hi": hi,
        "hint_m": [hint_x_cm / 100, hint_y_cm / 100],
    }, ensure_ascii=False)
