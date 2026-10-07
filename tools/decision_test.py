#!/usr/bin/env python3
"""Kartın kararlarını uçtan uca dener (Faz 2.6 c ve d).

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
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from link_test import (AGENT_PORT, KEY_FILE, ROOT, VEHICLE_PORT, Link, Report,   # noqa: E402
                       fr, m)
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
HEARTBEAT_PERIOD_S = 0.1


class Heartbeat:
    """Köprünün kalp atışı: 100 ms'de bir, istenince durur."""

    def __init__(self, link: Link) -> None:
        self.link = link
        self.running = False
        self.thread = None
        self.last_sent = 0.0

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """Durdurur ve son kalp atışının gönderildiği anı döndürür."""
        self.running = False
        self.thread.join()
        return self.last_sent

    def _run(self) -> None:
        while self.running:
            self.link.send(m.Heartbeat(int(time.monotonic() * 1000) & 0xFFFFFFFF))
            self.last_sent = time.monotonic()
            time.sleep(HEARTBEAT_PERIOD_S)


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

    print("Kalp atışı geri geldi")
    hb.start()
    time.sleep(0.5)
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    rep.check(ack is not None and ack[1].state == m.BoardState.HOLD,
              "HOLD mandallı: SIFIRLA olmadan NORMAL'e dönmedi")
    hb.stop()


if __name__ == "__main__":
    sys.exit(main())
