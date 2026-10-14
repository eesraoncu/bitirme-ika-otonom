#!/usr/bin/env python3
"""Kartın kararlarını uçtan uca dener (Faz 2.6 c ve d, Faz 4.1d kurtarma).

Kullanım:
    python3 tools/decision_test.py

Plandaki "bitti sayılır": elle gönderilen hedef izinli bölgedeyse CAN'den
geçip araç kanalından çıkıyor, dışındaysa gerekçeyle ajan kanalına dönüyor;
kalp atışı kesilince kart HOLD'a geçiyor.

Betik iki kanala da bağlanır. Kalp atışını köprü gibi arka planda 100 ms'de
bir gönderir ve gerektiğinde keser. Hedefler ve beklenen ipuçları kartın
sahasından hesaplanır: shared/site/ika_saha.yaml → tools/gen_site.py (K-037).
Kartta aynı YAML'dan üretilmiş site_data.c yüklü olmalı.

Kart TELEMETRY'yi araç kanalından alıp CAN'e koyar, bekçi düğümü CAN'den
alır: telemetri yaşının düşmesi ters yöndeki CAN yolunu da gösterir.

Kurtarma (RULES §5.2, K-047): araç konumu arka planda 50 ms'de bir gönderilir
(TelemetryStream), kart RECOVERY'de telemetri 500 ms gelmezse HOLD'a geçer.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from link_test import (AGENT_PORT, KEY_FILE, ROOT, VEHICLE_PORT, Link, Report,   # noqa: E402
                       fr, m)
from ika_protocol.link import HEARTBEAT_PERIOD_S, Heartbeat   # noqa: E402,F401
import gen_site as gs   # noqa: E402

# Hedefler kartın sahasından (cm). İzinli hedef: konteynerin önü, kuzeye bakarak
SITE = gs.load_site()
_safe = list(SITE["safe"].values())
_x, _y = SITE["safe"]["konteyner_onu"]
ALLOWED_GOAL = (_x, _y, 1571)
_kazi = SITE["forbidden"]["kazi"]
FORBIDDEN_GOAL = (sum(p[0] for p in _kazi) // len(_kazi), sum(p[1] for p in _kazi) // len(_kazi))
EDGE_GOAL = (max(p[0] for p in SITE["allowed"]), 0)          # izinli alanın doğu kenarı
OUTSIDE_GOAL = (5000, 0)


def hint(p):
    """Kartın vermesi gereken ipucu: hedefe en yakın güvenli nokta (RULES §5.3)."""
    return gs.nearest_safe(_safe, SITE["home"], p)


assert gs.geofence_cm(SITE["allowed"], list(SITE["forbidden"].values()), ALLOWED_GOAL[:2]) == gs.OK
VERDICT_WAIT_S = 0.5


def verdict_for(agent: Link, wire_seq: int):
    got = agent.wait_for(m.Verdict, VERDICT_WAIT_S, lambda v: v.ref_seq == wire_seq)
    return None if got is None else got[1]


def send_cmd(agent: Link, msg):
    # Sayaç gönderilen baytlardan okunur: kalp atışı arka planda gönderildiği
    # için agent.seq bu arada ilerlemiş olabilir.
    wire = agent.send(msg)
    seq = int.from_bytes(fr.cobs_decode(wire[:-1])[1:5], "little")
    return verdict_for(agent, seq)


def goto(x: int, y: int, yaw: int = 0) -> m.GotoCmd:
    # belief alanları tutarlılık kuralı içindir (Faz 4), henüz denetlenmiyor
    return m.GotoCmd(x, y, yaw, 0, 0, 0)


class TelemetryStream:
    """Araç köprüsünün yerine: araç kanalından 50 ms'de bir TELEMETRY (cm)."""

    PERIOD_S = 0.05

    def __init__(self, link: Link) -> None:
        self.link = link
        self.pos = (0, 0)
        self.running = False
        self.last_sent = 0.0
        self.thread = None

    def start(self, pos) -> None:
        self.pos = pos
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """Durdurur ve son telemetrinin gönderildiği anı döndürür."""
        self.running = False
        if self.thread is not None:
            self.thread.join()
        return self.last_sent

    def _run(self) -> None:
        while self.running:
            self.link.send(m.Telemetry(self.pos[0], self.pos[1], 0))
            self.last_sent = time.monotonic()
            time.sleep(self.PERIOD_S)


def reaches_state(agent: Link, state: m.BoardState) -> bool:
    """Tampondaki eski STATUS'lar yanıltmasın: bu durumu bildiren bir STATUS
    2,5 s içinde gelmeli (STATUS saniyede bir)."""
    return agent.wait_for(m.Status, 2.5, lambda st: st.state == state) is not None


def main() -> int:
    if not KEY_FILE.exists():
        print(f"{KEY_FILE.relative_to(ROOT)} yok. Önce: python3 tools/gen_key.py", file=sys.stderr)
        return 2
    key = KEY_FILE.read_bytes()
    rep = Report()
    agent = Link(AGENT_PORT, m.Channel.AGENT, key)
    vehicle = Link(VEHICLE_PORT, m.Channel.VEHICLE, key)
    hb = Heartbeat(agent)
    try:
        run(agent, vehicle, hb, rep)
    except (RuntimeError, fr.FrameError) as e:
        print(f"  [KALDI] {e}")
        rep.failed += 1
    finally:
        if hb.running:
            hb.stop()
    print("SONUÇ: " + ("hepsi geçti" if rep.failed == 0 else f"{rep.failed} denetim kaldı"))
    return 0 if rep.failed == 0 else 1


def run(agent: Link, vehicle: Link, hb: Heartbeat, rep: Report) -> None:
    print("Bağlantı")
    agent.connect()
    vehicle.connect()
    rep.check(agent.session_id == vehicle.session_id, "iki kanalda aynı oturum")

    # Önceki bir çalıştırma kartı NORMAL'de bırakmış olabilir: kalp atışı
    # yokken 500 ms içinde HOLD'a düşmeli.
    vehicle.receive(0.7)
    rep.check(reaches_state(agent, m.BoardState.HOLD), "kalp atışı yok: kart HOLD'da")

    print("HOLD")
    # Aralık kartın kendi zaman damgasından (ts_ms) ölçülür: bilgisayarın okuma
    # anı, tamponda birikmiş çerçeveleri aynı ana yığardı.
    frames = [f for f, c in vehicle.receive(1.0) if c is m.Drive]
    gaps = [b.ts_ms - a.ts_ms for a, b in zip(frames, frames[1:])]
    rep.check(len(gaps) >= 10 and all(45 <= g <= 55 for g in gaps), "araç kanalına 20 Hz sıfır hız",
              f"{len(frames)} DRIVE, aralık {min(gaps)}–{max(gaps)} ms" if gaps else "DRIVE yok")
    rep.check(all(m.Drive.unpack(f.payload).v_mm_s == 0 and m.Drive.unpack(f.payload).w_mrad_s == 0
                  for f in frames), "hepsi sıfır")

    v = send_cmd(agent, goto(*ALLOWED_GOAL))
    rep.check(v is not None and v.result == m.Result.REJECTED and v.rule == m.Rule.MODE
              and v.reason == m.Reason.IN_HOLD, "HOLD'da GOTO → MODE / IN_HOLD")
    v = send_cmd(agent, m.ResetCmd())
    rep.check(v is not None and v.reason == m.Reason.NO_HEARTBEAT,
              "kalp atışı yokken SIFIRLA → MODE / NO_HEARTBEAT")

    print("SIFIRLA")
    hb.start()
    time.sleep(0.3)
    v = send_cmd(agent, m.ResetCmd())
    rep.check(v is not None and v.result == m.Result.ACCEPTED, "kalp atışı varken SIFIRLA kabul")
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    rep.check(ack is not None and ack[1].state == m.BoardState.NORMAL, "HEARTBEAT_ACK: NORMAL")
    vehicle.receive(0.2)   # kuyrukta kalmış son DRIVE'lar
    drives = [c for _, c in vehicle.receive(0.5) if c is m.Drive]
    rep.check(not drives, "NORMAL'de sıfır hız akışı durdu", f"{len(drives)} DRIVE")
    v = send_cmd(agent, m.ResetCmd())
    rep.check(v is not None and v.reason == m.Reason.NOT_IN_HOLD, "NORMAL'de SIFIRLA → NOT_IN_HOLD")

    print("Hedefler")
    x, y, yaw = ALLOWED_GOAL
    v = send_cmd(agent, goto(x, y, yaw))
    rep.check(v is not None and v.result == m.Result.ACCEPTED, "izinli hedef kabul")
    got = vehicle.wait_for(m.Goal, 0.5)
    rep.check(got is not None and (got[1].x_cm, got[1].y_cm, got[1].yaw_mrad) == (x, y, yaw)
              and got[1].source == m.GoalSource.AGENT,
              "hedef CAN'den geçip araç kanalından çıktı", str(got[1]) if got else "gelmedi")

    for (gx, gy), reason, what in [
        (OUTSIDE_GOAL, m.Reason.GOAL_OUTSIDE_ALLOWED, "izinli alanın dışı"),
        (FORBIDDEN_GOAL, m.Reason.GOAL_IN_FORBIDDEN, "kazı alanının ortası"),
        (EDGE_GOAL, m.Reason.GOAL_OUTSIDE_ALLOWED, "izinli alanın kenarı"),
    ]:
        expect = hint((gx, gy))
        v = send_cmd(agent, goto(gx, gy))
        ok = (v is not None and v.result == m.Result.REJECTED and v.rule == m.Rule.GEOFENCE
              and v.reason == reason and (v.hint_x_cm, v.hint_y_cm) == expect)
        rep.check(ok, f"{what} {gx, gy} → GEOFENCE / {reason.name}, ipucu {expect}",
                  "" if v is None else f"{v.reason.name}, ({v.hint_x_cm}, {v.hint_y_cm})")
    goals = [c for _, c in vehicle.receive(0.3) if c is m.Goal]
    rep.check(not goals, "reddedilen hedefler araca gitmedi", f"{len(goals)} GOAL")
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    rep.check(ack is not None and ack[1].reject_streak == 3, "üst üste 3 içerik reddi",
              f"reject_streak {ack[1].reject_streak}" if ack else "")

    print("Telemetri (araç kanalı → CAN → bekçi)")
    vehicle.send(m.Telemetry(-45, 812, -3000))
    time.sleep(0.05)
    st = agent.wait_for(m.Status, 2.5, lambda s: s.telemetry_age_ms < 1100)
    rep.check(st is not None, "telemetri yaşı düştü", f"{st[1].telemetry_age_ms} ms" if st else "")

    print("Hız komutu (K-031)")
    vehicle.receive(0.2)
    agent.send(m.VelocityCmd(300, 100))
    got = vehicle.wait_for(m.Drive, 0.5)
    rep.check(got is not None and (got[1].v_mm_s, got[1].w_mrad_s) == (300, 100),
              "NORMAL'de VELOCITY_CMD aynen DRIVE olarak araca", str(got[1]) if got else "gelmedi")
    rep.check(agent.wait_for(m.Verdict, 0.3) is None, "VELOCITY_CMD'ye VERDICT yok")

    print("Kalp atışı kesildi")
    vehicle.receive(0.2)   # tampon boşalsın: ilk DRIVE kesintiden sonrakini göstersin
    last = hb.stop()
    got = vehicle.wait_for(m.Drive, 1.5)
    gap_ms = (time.monotonic() - last) * 1000 if got else None
    rep.check(got is not None and 480 <= gap_ms <= 650,
              "son kalp atışından ~500 ms sonra sıfır hız başladı",
              f"{gap_ms:.0f} ms" if gap_ms else "gelmedi")
    rep.check(reaches_state(agent, m.BoardState.HOLD), "kart HOLD'da")
    v = send_cmd(agent, goto(*ALLOWED_GOAL))
    rep.check(v is not None and v.reason == m.Reason.IN_HOLD, "HOLD'da hedef reddedildi")
    vehicle.receive(0.2)
    agent.send(m.VelocityCmd(300, 100))
    drives = [m.Drive.unpack(f.payload) for f, c in vehicle.receive(0.5) if c is m.Drive]
    rep.check(drives and all((d.v_mm_s, d.w_mrad_s) == (0, 0) for d in drives),
              "HOLD'da VELOCITY_CMD araca gitmedi, yalnız sıfır hız", f"{len(drives)} DRIVE")

    print("Kalp atışı geri geldi")
    hb.start()
    time.sleep(0.5)
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    rep.check(ack is not None and ack[1].state == m.BoardState.HOLD,
              "HOLD mandallı: SIFIRLA olmadan NORMAL'e dönmedi")

    tel = TelemetryStream(vehicle)
    try:
        recovery(agent, vehicle, tel, rep)
    finally:
        tel.stop()
    hb.stop()


def board_state(agent: Link):
    """Kartın şimdiki durumu. Tamponda geçişten önceki HEARTBEAT_ACK'ler birikmiş
    olabilir: önce boşaltılır, sonraki cevap (100 ms içinde) okunur."""
    agent.receive(0.12)
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    return None if ack is None else ack[1].state


def reset_to_normal(agent: Link, rep: Report) -> None:
    v = send_cmd(agent, m.ResetCmd())
    rep.check(v is not None and v.result == m.Result.ACCEPTED, "SIFIRLA → NORMAL")


def wait_goal(vehicle: Link, source: m.GoalSource):
    got = vehicle.wait_for(m.Goal, 0.5, lambda g: g.source == source)
    return None if got is None else got[1]


def holds_with_zero_drive(agent: Link, vehicle: Link) -> bool:
    vehicle.receive(0.1)
    drives = [m.Drive.unpack(f.payload) for f, c in vehicle.receive(0.3) if c is m.Drive]
    return (board_state(agent) == m.BoardState.HOLD and len(drives) >= 4
            and all((d.v_mm_s, d.w_mrad_s) == (0, 0) for d in drives))


def recovery(agent: Link, vehicle: Link, tel: TelemetryStream, rep: Report) -> None:
    # Hedefler kartın sahasından: araç kazının ortasındayken en yakın güvenli nokta
    inside_forbidden = FORBIDDEN_GOAL
    safe = hint(inside_forbidden)
    home = SITE["home"]
    away_from_home = ALLOWED_GOAL[:2]

    print("Kurtarma 1: araç yasak bölgede (RULES §5.2)")
    reset_to_normal(agent, rep)
    vehicle.receive(0.2)
    tel.start(inside_forbidden)
    g = wait_goal(vehicle, m.GoalSource.RECOVERY_SAFE)
    rep.check(g is not None and (g.x_cm, g.y_cm) == safe,
              f"araç {inside_forbidden} → GOAL en yakın güvenli nokta {safe}, RECOVERY_SAFE",
              str(g) if g else "gelmedi")
    rep.check(board_state(agent) == m.BoardState.RECOVERY, "kart RECOVERY'de")
    v = send_cmd(agent, goto(*ALLOWED_GOAL))
    rep.check(v is not None and v.rule == m.Rule.MODE and v.reason == m.Reason.IN_RECOVERY,
              "RECOVERY'de GOTO → MODE / IN_RECOVERY")
    agent.send(m.VelocityCmd(300, 100))
    got = vehicle.wait_for(m.Drive, 0.5, lambda d: (d.v_mm_s, d.w_mrad_s) == (300, 100))
    rep.check(got is not None, "RECOVERY'de VELOCITY_CMD araca geçiyor (Nav2 götürür)")
    tel.pos = (safe[0] + 21, safe[1] + 28)            # 21² + 28² = 35²: sınır dahil
    time.sleep(0.2)
    rep.check(holds_with_zero_drive(agent, vehicle), "hedefe 35 cm: HOLD, 20 Hz sıfır hız")
    tel.stop()

    print("Kurtarma 2: telemetri kesildi (K-047)")
    reset_to_normal(agent, rep)
    tel.start(inside_forbidden)
    rep.check(wait_goal(vehicle, m.GoalSource.RECOVERY_SAFE) is not None, "RECOVERY'ye girdi")
    vehicle.receive(0.1)
    last = tel.stop()
    got = vehicle.wait_for(m.Drive, 1.5, lambda d: (d.v_mm_s, d.w_mrad_s) == (0, 0))
    gap_ms = (time.monotonic() - last) * 1000 if got else None
    rep.check(got is not None and 480 <= gap_ms <= 650,
              "son telemetriden ~500 ms sonra HOLD ve sıfır hız",
              f"{gap_ms:.0f} ms" if gap_ms else "gelmedi")
    rep.check(board_state(agent) == m.BoardState.HOLD, "kart HOLD'da")

    print("Kurtarma 3: üst üste 5 içerik reddi (RULES §5.4)")
    reset_to_normal(agent, rep)
    tel.start(away_from_home)
    time.sleep(0.2)
    vehicle.receive(0.1)
    verdicts = [send_cmd(agent, goto(*FORBIDDEN_GOAL)) for _ in range(4)]
    early = [c for _, c in vehicle.receive(0.2) if c is m.Goal]
    rep.check(all(v is not None and v.rule == m.Rule.GEOFENCE for v in verdicts) and not early,
              "ilk 4 ret: GEOFENCE, araca hedef yok", f"{len(early)} GOAL")
    v = send_cmd(agent, goto(*FORBIDDEN_GOAL))
    rep.check(v is not None and v.rule == m.Rule.GEOFENCE, "5. ret yine ajana VERDICT olarak döndü")
    g = wait_goal(vehicle, m.GoalSource.RECOVERY_HOME)
    rep.check(g is not None and (g.x_cm, g.y_cm) == home,
              f"5. ret → GOAL başlangıç {home}, RECOVERY_HOME", str(g) if g else "gelmedi")
    rep.check(board_state(agent) == m.BoardState.RECOVERY, "kart RECOVERY'de")
    tel.pos = home
    time.sleep(0.2)
    rep.check(holds_with_zero_drive(agent, vehicle), "başlangıca vardı: HOLD")


if __name__ == "__main__":
    sys.exit(main())
