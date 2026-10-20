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
from typing import Optional, Tuple

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
    """VERDICT → /guard/verdict'e yazılan JSON: her yapılandırmada tam (deney kaydı, S1).
    Ajanın gördüğü metin feedback_text'te (C/D, protocol §7.3)."""
    return json.dumps({
        "ref_seq": ref_seq, "result": result, "rule": rule, "reason": reason,
        "value": value, "lo": lo, "hi": hi,
        "hint_m": [hint_x_cm / 100, hint_y_cm / 100],
    }, ensure_ascii=False)


# ---- Ajanın görev arayüzü (/guard/task → kart → /guard/feedback, Faz 4.2) ------------

U16_MAX = 65535
U32 = 0xFFFFFFFF
TASK_CMDS = ("git", "bekle", "hiz_siniri", "dur")


class TaskError(ValueError):
    """Görev JSON'u anlaşılamadı: karta hiçbir şey gönderilmez, ajana metin döner."""


def _number(task: dict, key: str) -> float:
    v = task.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise TaskError(f"'{key}' sayı olmalı")
    return float(v)


def parse_task(text: str) -> dict:
    """/guard/task JSON'u → doğrulanmış sözlük (id, cmd, alanlar; inanç dur dışında şart).
    Örnek: {"id": "g7", "cmd": "git", "x": 8.5, "y": 1.0, "yaw": 0.0,
            "belief": {"x": 0.0, "y": 0.0, "stamp": 12.5}}"""
    try:
        task = json.loads(text)
    except json.JSONDecodeError as e:
        raise TaskError(f"JSON değil ({e.msg})") from None
    if not isinstance(task, dict):
        raise TaskError("JSON nesnesi olmalı")
    out = {"id": str(task.get("id", "")), "cmd": task.get("cmd")}
    if out["cmd"] not in TASK_CMDS:
        raise TaskError(f"'cmd' şunlardan biri olmalı: {', '.join(TASK_CMDS)}")
    if out["cmd"] == "git":
        out.update(x=_number(task, "x"), y=_number(task, "y"), yaw=float(task.get("yaw", 0.0)))
        if not math.isfinite(out["yaw"]):
            raise TaskError("'yaw' sayı olmalı")
    elif out["cmd"] == "bekle":
        out["sure_s"] = _number(task, "sure_s")
        if not 0 < out["sure_s"] <= U16_MAX:
            raise TaskError(f"'sure_s' 0'dan büyük, en çok {U16_MAX} olmalı")
    elif out["cmd"] == "hiz_siniri":
        out["deger_mps"] = _number(task, "deger_mps")
    if out["cmd"] != "dur":
        b = task.get("belief")
        if not isinstance(b, dict):
            raise TaskError("'belief' (x, y, stamp) gerekli: aracın konumu ve okunduğu an (ROS zamanı)")
        out["belief"] = {k: _number(b, k) for k in ("x", "y", "stamp")}
    return out


def task_id(text: str) -> str:
    """Anlaşılamayan görevin id'si, okunabiliyorsa (ajan hatayı komutuyla eşleştirsin)."""
    try:
        task = json.loads(text)
    except json.JSONDecodeError:
        return ""
    return str(task.get("id", "")) if isinstance(task, dict) else ""


def ros_to_board_ms(stamp_s: float, ros_now_s: float, board_now_ms: int) -> int:
    """ROS zamanındaki bir an → kartın saat alanı (protocol §6.3: dönüşüm köprünün işi).
    Kartın şimdiki tahmini eksi o anın ne kadar önce olduğu; 32 bit sarar."""
    return (board_now_ms - round((ros_now_s - stamp_s) * 1000)) & U32


def task_args(task: dict, belief_ts_board: int) -> Tuple:
    """Doğrulanmış görev → protokol alanları (tamsayı). İlk eleman komut adı."""
    cmd = task["cmd"]
    if cmd == "dur":
        return ("dur",)
    b = task["belief"]
    belief = (to_int16(b["x"], 100), to_int16(b["y"], 100), belief_ts_board)
    if cmd == "git":
        return ("git", to_int16(task["x"], 100), to_int16(task["y"], 100),
                to_int16(wrap_angle(task["yaw"]), 1000), *belief)
    if cmd == "bekle":
        return ("bekle", min(U16_MAX, round(task["sure_s"])), *belief)
    mm = round(task["deger_mps"] * 1000)              # LIMIT'i kart denetler, burada kırpılmaz
    return ("hiz_siniri", max(0, min(U16_MAX, mm)), *belief)


def task_error_text(error: TaskError) -> str:
    """Anlaşılamayan görevde ajanın gördüğü metin. Kartlı ve kartsız köprüde aynı."""
    return f"Görev anlaşılamadı: {error}. Karta gönderilmedi."


def direct_action(task: dict) -> Tuple:
    """Kartsız yapılandırmalar (A/B, K-054): doğrulanmış görev → Nav2'de ne yapılacağı.
    Kartlı yoldaki yuvarlamadan geçer (task_args → GOAL, cm_to_pose): Nav2'ye aynı hedef gider.
      ("hedef", x, y, qz, qw)
      ("iptal",)          bekle ve dur: kartlı yolda WAIT/STOP → HALT → Nav2 hedefi iptal (K-042)
      ("hiz_siniri", m/s) kartlı yolda SPEED_LIMIT_SET → /speed_limit; burada LIMIT denetimi yok"""
    kind, *args = task_args(task, 0)
    if kind == "git":
        return ("hedef", *cm_to_pose(*args[:3]))
    if kind == "hiz_siniri":
        return ("hiz_siniri", args[0] / 1000.0)
    return ("iptal",)


def safe_point_name(x_cm: int, y_cm: int, safe_points: dict) -> Optional[str]:
    """İpucu bir kayıtlı güvenli noktaysa adı (K-044). safe_points: ad → (x_cm, y_cm)."""
    for name, (sx, sy) in safe_points.items():
        if (sx, sy) == (x_cm, y_cm):
            return name
    return None


def _m(cm: int) -> str:
    return f"{cm / 100:.2f}".replace(".", ",")


def _mps(mm_s: int) -> str:
    return f"{mm_s / 1000:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def feedback_text(result: str, rule: str, reason: str, value: int, lo: int, hi: int,
                  hint_x_cm: int, hint_y_cm: int, *, full: bool,
                  safe_points: Optional[dict] = None) -> str:
    """Ajanın göreceği Türkçe metin. full=False: C yapılandırması, gerekçe gizli
    (protocol §7.3). Ondalık virgül, koordinatlar "(x; y)" m (protocol §7.3 örneği)."""
    if result == "ACCEPTED":
        return "Komut kabul edildi."
    if not full:
        return "Komut reddedildi."
    head = f"Komut reddedildi ({rule} / {reason})."
    if reason in ("GOAL_IN_FORBIDDEN", "GOAL_OUTSIDE_ALLOWED"):
        where = "yasak bölgede" if reason == "GOAL_IN_FORBIDDEN" else "izinli alanın dışında"
        name = safe_point_name(hint_x_cm, hint_y_cm, safe_points or {})
        point = f"{name} ({_m(hint_x_cm)}; {_m(hint_y_cm)})" if name else \
            f"({_m(hint_x_cm)}; {_m(hint_y_cm)})"
        detail = f"Hedef {where}. En yakın güvenli nokta: {point}."
    elif reason == "ABOVE_MAX":
        detail = (f"İstenen hız sınırı {_mps(value)} m/s, izinli aralık {_mps(lo)}–{_mps(hi)} m/s.")
    elif reason == "NOT_POSITIVE":
        detail = f"Hız sınırı 0'dan büyük olmalı, izinli aralık {_mps(lo)}–{_mps(hi)} m/s."
    elif reason == "TOO_FAR":
        detail = (f"Varsaydığın konum telemetriden {_m(value)} m uzak, tolerans {_m(hi)} m. "
                  f"Aracın şu anki konumu: ({_m(hint_x_cm)}; {_m(hint_y_cm)}).")
    elif reason == "BELIEF_TOO_OLD":
        age = f"{value / 1000:.1f}".replace(".", ",")
        detail = f"Konum bilgin {age} s eski, en çok {hi // 1000} s olmalı: konumu yeniden oku."
    elif reason == "BELIEF_FROM_FUTURE":
        detail = f"Konum bilginin zamanı {-value} ms ileride: konumu yeniden oku."
    elif reason == "NO_TELEMETRY":
        detail = (f"Araçtan {value} ms'dir konum gelmiyor (en çok {hi} ms): tutarlılık "
                  f"denetlenemedi, biraz sonra yeniden dene.")
    elif reason == "TOO_OLD":
        detail = f"Komut karta {value} ms'de ulaştı, en çok {hi} ms olmalı: yeniden gönder."
    elif reason == "FROM_FUTURE":
        detail = f"Komutun zaman damgası kartın saatinden {-value} ms ileride (en çok {-lo} ms)."
    elif reason == "IN_HOLD":
        detail = "Kart beklemede (HOLD): komut kabul edilmiyor, operatörün SIFIRLA'sı gerekir."
    elif reason == "IN_RECOVERY":
        detail = ("Kart kurtarma modunda (RECOVERY): araç güvenli noktaya götürülüyor, "
                  "komut kabul edilmiyor.")
    else:
        detail = ""
    return f"{head} {detail}".strip()
