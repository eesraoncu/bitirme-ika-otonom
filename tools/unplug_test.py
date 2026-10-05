#!/usr/bin/env python3
"""Ajan kablosu fiziksel olarak çekilince kartın tepkisini dener (Faz 2.6 d).

Kullanım:
    python3 tools/unplug_test.py

ÖNCE: kart E5V'den beslenmeli (JP5 [5-6], CP2102'nin 5V pini → CN7 pin 6,
UM2505 §7.4). Yoksa kablo çekilince kart da kapanır.

decision_test.py kalp atışını yazılımla keser. Burada ajan kanalının USB'si
(CN1) çekilir: port kaybolur, ST-LINK'in karta giden seri hatları kopar.
Betik kopmaya dayanır, araç kanalını izler ve kablo geri takılınca ajan
portunu yeniden açar.

Ölçülen:
- Son kalp atışından ilk sıfır hıza geçen süre, kartın kendi saatinden:
  son HEARTBEAT_ACK'in ts_ms'i ile ilk DRIVE'ın ts_ms'i. Bilgisayarın son
  başarılı yazma anı yalnızca bilgi için verilir: kablo çekilirken yazma bir
  süre işletim sisteminin tamponuna "başarıyla" gidebilir.
- Kartın yeniden başlamadığı: araç kanalında aynı oturum, kartın saati
  ilerliyor, sayaçlar sıfırlanmadı; kablo geri gelince ajan kanalında da
  aynı oturum.
- Kopma sırasında ajan kanalına çöp bayt gelip gelmediği: STATUS hata
  sayaçlarının farkı. Bu bir sonuçtur, test bununla kalmaz.
"""
from __future__ import annotations

import select
import sys
import termios
import threading
import time
from pathlib import Path
from typing import Optional

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent))

from decision_test import HEARTBEAT_PERIOD_S, Heartbeat, send_cmd   # noqa: E402
from link_test import (AGENT_PORT, KEY_FILE, ROOT, VEHICLE_PORT, Link, Report,   # noqa: E402
                       fr, m)

PULL_WAIT_S = 60.0       # Enter'dan sonra kabloyu çekmek için verilen süre
REPLUG_WAIT_S = 60.0     # Enter'dan sonra portun geri gelmesi için verilen süre
REPLUG_WATCH_S = 2.0     # Enter'dan sonra araç kanalının izlenmeye devam ettiği süre
DRIVE_WATCH_S = 2.0      # ilk sıfır hızdan sonra izlenen süre
LINK_LOST = (serial.SerialException, OSError, termios.error, fr.FrameError)
ERR_FIELDS = ("err_framing", "err_crc", "err_type", "err_auth", "err_replay", "err_fresh")


def u32_diff(a: int, b: int) -> int:
    """Kartın saati uint32: b - a, taşma dahil."""
    return (b - a) & 0xFFFFFFFF


class Keepalive:
    """Kablo çekilene kadar kalp atışı gönderir ve HEARTBEAT_ACK'leri okur.

    Ajan kanalını yalnızca bu iş parçacığı kullanır. Port kaybolunca durur;
    son ACK'in kart saatindeki anını ve son başarılı yazmanın anını saklar."""

    def __init__(self, link: Link) -> None:
        self.link = link
        self.last_ack_ts: Optional[int] = None
        self.last_sent = 0.0
        self.error: Optional[str] = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def alive(self) -> bool:
        return self.thread.is_alive()

    def _run(self) -> None:
        try:
            while True:
                self.link.send(m.Heartbeat(int(time.monotonic() * 1000) & 0xFFFFFFFF))
                self.last_sent = time.monotonic()
                end = time.monotonic() + HEARTBEAT_PERIOD_S
                while (left := end - time.monotonic()) > 0:
                    got = self.link.wait_for(m.HeartbeatAck, left)
                    if got is not None:
                        self.last_ack_ts = got[0].ts_ms
        except LINK_LOST as e:
            self.error = f"{type(e).__name__}: {e}"


def enter_pressed() -> bool:
    """Enter'a basıldıysa satırı okur. Beklemez: araç kanalı okunmaya devam
    etmeli, yoksa biriken HELLO ve STATUS'lar tamponu taşırır."""
    if select.select([sys.stdin], [], [], 0)[0]:
        sys.stdin.readline()
        return True
    return False


def open_agent(key: bytes) -> Link:
    """Kablo geri takılınca ajan portunu açar. by-id yolu USB yeniden
    tanınınca da aynı kalır."""
    end = time.monotonic() + REPLUG_WAIT_S
    while time.monotonic() < end:
        if Path(AGENT_PORT).exists():
            time.sleep(1.0)   # ST-LINK tanınmayı bitirsin
            try:
                return Link(AGENT_PORT, m.Channel.AGENT, key)
            except serial.SerialException:
                pass
        time.sleep(0.2)
    raise RuntimeError("ajan portu geri gelmedi")


def main() -> int:
    if not KEY_FILE.exists():
        print(f"{KEY_FILE.relative_to(ROOT)} yok. Önce: python3 tools/gen_key.py", file=sys.stderr)
        return 2
    key = KEY_FILE.read_bytes()
    rep = Report()
    try:
        run(key, rep)
    except (RuntimeError, fr.FrameError) as e:
        print(f"  [KALDI] {e}")
        rep.failed += 1
    print("SONUÇ: " + ("hepsi geçti" if rep.failed == 0 else f"{rep.failed} denetim kaldı"))
    return 0 if rep.failed == 0 else 1


def run(key: bytes, rep: Report) -> None:
    print("Hazırlık")
    agent = Link(AGENT_PORT, m.Channel.AGENT, key)
    vehicle = Link(VEHICLE_PORT, m.Channel.VEHICLE, key)
    agent.connect()
    vehicle.connect()
    session = agent.session_id
    rep.check(vehicle.session_id == session, "iki kanalda aynı oturum", f"0x{session:08X}")
    # Gerçek araç gibi telemetri gönderilir: araç kanalı kurulur, kart oraya
    # HELLO yayınlamayı keser ve frames_ok sayacı anlam kazanır.
    vehicle.send(m.Telemetry(-45, 812, -3000))

    hb = Heartbeat(agent)
    hb.start()
    time.sleep(0.3)
    v = send_cmd(agent, m.ResetCmd())
    # Kart HOLD'daysa SIFIRLA kabul edilir, zaten NORMAL'deyse NOT_IN_HOLD döner
    rep.check(v is not None and (v.result == m.Result.ACCEPTED or v.reason == m.Reason.NOT_IN_HOLD),
              "SIFIRLA", "cevap yok" if v is None else v.reason.name)
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    rep.check(ack is not None and ack[1].state == m.BoardState.NORMAL, "kart NORMAL'de")
    if ack is None or ack[1].state != m.BoardState.NORMAL:
        hb.stop()
        print("  Kart NORMAL'e geçmedi, kablo çekmeye geçilmiyor.")
        return
    before = agent.status()
    hb.stop()
    # Kalp atışı Keepalive'a geçer; aradaki boşluk 100 ms'den kısa
    keep = Keepalive(agent)
    keep.start()
    veh_before = vehicle.status()
    vehicle.receive(0.2)

    print("\n>>> Hazır olunca Enter'a bas, sonra kartın USB kablosunu (CN1) çek.\n")
    drives = []
    first_drive_pc = 0.0   # ilk DRIVE'ın bilgisayara geldiği an (yalnızca bilgi)
    reboot = None
    end = None             # Enter'a basılınca başlar
    while end is None or time.monotonic() < end:
        if end is None and enter_pressed():
            end = time.monotonic() + PULL_WAIT_S
            print(f">>> Şimdi çek. {PULL_WAIT_S:.0f} s bekleniyor.")
        try:
            got = vehicle.receive(0.1)
        except fr.FrameError as e:
            reboot = f"araç kanalında doğrulanamayan çerçeve ({e})"
            break
        for f, cls in got:
            # Araç kanalından çerçeve gönderilmediği için kart oraya 500 ms'de
            # bir HELLO yayınlar (channel.c). Yeniden başlamanın işareti HELLO
            # değil, HELLO'daki oturum kimliğinin değişmesi.
            if cls is m.Hello:
                sid = m.Hello.unpack(f.payload).session_id
                if sid != session:
                    reboot = f"araç kanalında yeni oturum 0x{sid:08X}"
            elif cls is m.Drive:
                if not drives:
                    first_drive_pc = time.monotonic()
                drives.append(f)
        if reboot or (drives and u32_diff(drives[0].ts_ms, drives[-1].ts_ms) >= DRIVE_WATCH_S * 1000):
            break
    keep_alive = keep.alive()

    print("Kopma")
    if keep_alive and drives:
        rep.check(False, "ajan portu koptu", "kablo çekilmeden sıfır hız başladı (kart HOLD'a geçti)")
    else:
        rep.check(not keep_alive, "ajan portu koptu", keep.error or "kablo çekilmedi")
    rep.check(reboot is None, "araç kanalında aynı oturum sürüyor", reboot or "")
    if keep_alive or not drives or keep.last_ack_ts is None:
        rep.check(False, "sıfır hız başladı",
                  f"{len(drives)} DRIVE, son ACK {'yok' if keep.last_ack_ts is None else 'var'}")
        return
    first = drives[0]
    gap_board = u32_diff(keep.last_ack_ts, first.ts_ms)
    rep.check(gap_board < 0x80000000, "kartın saati ilerledi (yeniden başlamadı)",
              f"son ACK {keep.last_ack_ts} ms, ilk DRIVE {first.ts_ms} ms")
    rep.check(480 <= gap_board <= 650, "son kalp atışından ~500 ms sonra sıfır hız (kartın saati)",
              f"{gap_board} ms")
    gaps = [u32_diff(a.ts_ms, b.ts_ms) for a, b in zip(drives, drives[1:])]
    rep.check(len(gaps) >= 10 and all(45 <= g <= 55 for g in gaps), "araç kanalına 20 Hz",
              f"{len(drives)} DRIVE, aralık {min(gaps)}–{max(gaps)} ms" if gaps else "tek DRIVE")
    rep.check(all(m.Drive.unpack(f.payload).v_mm_s == 0 and m.Drive.unpack(f.payload).w_mrad_s == 0
                  for f in drives), "hepsi sıfır")
    veh_after = vehicle.status()
    rep.check(veh_after.state == m.BoardState.HOLD, "araç kanalındaki STATUS: HOLD",
              veh_after.state.name)
    rep.check(veh_after.frames_ok >= veh_before.frames_ok, "araç kanalı sayaçları sıfırlanmadı",
              f"frames_ok {veh_before.frames_ok} → {veh_after.frames_ok}")
    print(f"  (bilgi) bilgisayarın saatiyle son başarılı yazmadan ilk DRIVE'a: "
          f"{(first_drive_pc - keep.last_sent) * 1000:.0f} ms; port hatası: {keep.error}")

    # Kablo geri takılırken de araç kanalı izlenir: kart yeniden başlarsa
    # yeni oturumun HELLO'su hangi anda geldi, ajan portu geri geldikten kaç
    # ms sonra?
    print("\n>>> Kabloyu geri tak, sonra Enter'a bas.\n")
    port_back = None    # ajan portu (by-id yolu) yeniden göründüğü an
    reboot_at = None
    reboot = None
    end = None          # Enter'a basılınca başlar
    while end is None or time.monotonic() < end:
        if end is None and enter_pressed():
            end = time.monotonic() + REPLUG_WATCH_S
        if port_back is None and Path(AGENT_PORT).exists():
            port_back = time.monotonic()
        try:
            got = vehicle.receive(0.05)
        except fr.FrameError as e:
            # Yeniden başlarken yarıda kalan çerçeve
            got = []
            if reboot is None:
                reboot_at, reboot = time.monotonic(), f"doğrulanamayan çerçeve ({e})"
        for f, cls in got:
            if cls is m.Hello:
                sid = m.Hello.unpack(f.payload).session_id
                if sid != session and vehicle.session_id != sid:
                    if reboot_at is None:
                        reboot_at = time.monotonic()
                    reboot = f"yeni oturum 0x{sid:08X}"
                    vehicle.session_id = sid   # sonraki çerçeveler yeni oturumla
    print("Geri bağlantı")
    if reboot is None:
        rep.check(True, "kablo geri takılırken kart yeniden başlamadı")
    elif port_back is None:
        rep.check(False, "kablo geri takılırken kart yeniden başlamadı", f"{reboot}, ajan portu henüz yok")
    else:
        rep.check(False, "kablo geri takılırken kart yeniden başlamadı",
                  f"{reboot}, ajan portu göründükten {(reboot_at - port_back) * 1000:+.0f} ms sonra")
    agent = open_agent(key)
    agent.connect()
    rep.check(agent.session_id == session, "ajan kanalında aynı oturum (kart hiç kapanmadı)",
              f"0x{agent.session_id:08X}")
    after = agent.status()
    if reboot is not None:
        print("  (not) kart yeniden başladığı için hata sayaçları ve HOLD mandalı ölçülemedi")
        return
    deltas = {n: (getattr(after, n) - getattr(before, n)) & 0xFFFF for n in ERR_FIELDS}
    print("  (sonuç) kopma boyunca ajan kanalı hata sayaçları: "
          + ", ".join(f"{n} +{d}" for n, d in deltas.items()))
    rep.check(after.state == m.BoardState.HOLD, "kart hâlâ HOLD'da", after.state.name)
    hb = Heartbeat(agent)
    hb.start()
    time.sleep(0.5)
    ack = agent.wait_for(m.HeartbeatAck, 0.5)
    hb.stop()
    rep.check(ack is not None and ack[1].state == m.BoardState.HOLD,
              "kalp atışı geri geldi, SIFIRLA olmadan NORMAL'e dönmedi")


if __name__ == "__main__":
    sys.exit(main())
