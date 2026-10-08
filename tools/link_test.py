#!/usr/bin/env python3
"""Kartın protokol katmanını uçtan uca dener (Faz 2.6 a).

Kullanım:
    python3 tools/link_test.py                  # ajan ve araç kanalı
    python3 tools/link_test.py --no-vehicle     # yalnızca ajan kanalı

Betik karta köprü gibi bağlanır: HELLO'dan oturum kimliğini öğrenir, gerçek
anahtarla (secrets/hmac_key.bin) imzalı mesaj gönderir. Ardından bilerek
bozuk mesajlar gönderir: tekrar oynatılmış, yanlış anahtarla ya da eski
oturumla imzalanmış, CRC'si bozuk, yanlış kanala ait, taşan. Kartın bunlara
cevap VERMEDİĞİNİ ve STATUS'taki doğru sayacı artırdığını denetler
(docs/protocol.md §4.7).

Kart yeni açıldıysa HELLO'yu kendisi yayınlar. Daha önce bir oturum
kurulduysa betik HELLO_REQ ile ister. İki durumda da çalışır.

Önce aynı portu açan programları (minicom, echo_test.py) kapatın.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared" / "protocol" / "python"))

from ika_protocol import frame as fr   # noqa: E402
from ika_protocol import messages as m   # noqa: E402
from ika_protocol.link import (AGENT_PORT, KEY_FILE, REPLY_WAIT_S, ROOT,   # noqa: E402,F401
                               VEHICLE_PORT, Link)


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def check(self, ok: bool, what: str, detail: str = "") -> None:
        print(f"  [{'GEÇTİ' if ok else 'KALDI'}] {what}" + (f": {detail}" if detail else ""))
        if not ok:
            self.failed += 1


def corrupt_crc(wire: bytes) -> bytes:
    """Yükün bir bitini çevirir, CRC'yi düzeltmez. COBS yeniden yapılır ki
    çerçeve sınırları sağlam kalsın ve hata CRC'de yakalansın."""
    raw = bytearray(fr.cobs_decode(wire[:-1]))
    raw[m.HEADER_BYTES] ^= 0x01
    return fr.cobs_encode(bytes(raw)) + bytes([m.FRAME_DELIMITER])


# Kendiliğinden akan mesajlar: HELLO yayını, saniyede bir STATUS, HOLD'da araç
# kanalına 20 Hz sıfır hız (docs/RULES.md §5.2).
BACKGROUND = (m.Status, m.Hello, m.Drive)


def no_reply(link: Link, what: str, rep: Report) -> None:
    """Hatalı mesaja cevap gelmemeli. Kendiliğinden akan mesajlar sayılmaz."""
    others = [c.NAME for _, c in link.receive(REPLY_WAIT_S) if c not in BACKGROUND]
    rep.check(not others, f"{what}: cevap yok", ", ".join(others) if others else "")


def test_agent(link: Link, rep: Report) -> int:
    print("Ajan kanalı")
    hello, how = link.connect()
    rep.check(True, f"HELLO geldi ({how})", f"session_id 0x{hello.session_id:08X}, "
              f"last_rx_seq {hello.last_rx_seq}")
    rep.check(hello.schema_hash == m.SCHEMA_HASH, "şema özeti aynı", f"0x{hello.schema_hash:08X}")
    rep.check(hello.state == m.BoardState.HOLD, "kart HOLD'da", hello.state.name)

    # İmzalı HEARTBEAT → HEARTBEAT_ACK, aynı echo değeriyle
    echo = int(time.monotonic() * 1000) & 0xFFFFFFFF
    hb_wire = link.send(m.Heartbeat(echo))
    got = link.wait_for(m.HeartbeatAck, REPLY_WAIT_S, lambda a: a.echo_pc_ms == echo)
    rep.check(got is not None, "imzalı HEARTBEAT → HEARTBEAT_ACK")

    before = link.status()
    expect = {"err_replay": 0, "err_auth": 0, "err_crc": 0, "err_type": 0, "err_framing": 0}

    link.write(hb_wire)   # aynı bayt dizisi, aynı sayaç
    no_reply(link, "aynı HEARTBEAT tekrar oynatıldı", rep)
    expect["err_replay"] += 1

    wrong_key = os.urandom(32)
    link.write(link.encode(link.frame(m.Heartbeat(1)), key=wrong_key))
    no_reply(link, "yanlış anahtarla imzalı", rep)
    expect["err_auth"] += 1

    # Önceki açılışın mesajı: doğru anahtar, başka oturum kimliği (§5.2)
    link.write(link.encode(link.frame(m.Heartbeat(2)), session_id=link.session_id ^ 1))
    no_reply(link, "başka oturumla imzalı", rep)
    expect["err_auth"] += 1

    link.write(corrupt_crc(link.encode(link.frame(m.Heartbeat(3)))))
    no_reply(link, "bir biti bozuk", rep)
    expect["err_crc"] += 1

    # Ajan tarafı aracın konumunu uyduramaz: TELEMETRY yalnızca araç kanalından
    link.send(m.Telemetry(100, 200, 300))
    no_reply(link, "TELEMETRY ajan kanalından", rep)
    expect["err_type"] += 1

    link.write(bytes([0x01]) * 70 + bytes([m.FRAME_DELIMITER]))
    no_reply(link, "70 baytlık taşan çerçeve", rep)
    expect["err_framing"] += 1

    # Reddedilenlerden sonra geçerli mesaj yine kabul edilmeli
    echo2 = (echo + 1) & 0xFFFFFFFF
    link.send(m.Heartbeat(echo2))
    got = link.wait_for(m.HeartbeatAck, REPLY_WAIT_S, lambda a: a.echo_pc_ms == echo2)
    rep.check(got is not None, "reddedilenlerden sonra geçerli HEARTBEAT kabul edildi")

    after = link.status()
    for name, n in expect.items():
        d = (getattr(after, name) - getattr(before, name)) & 0xFFFF
        rep.check(d == n, f"STATUS.{name} +{n}", f"+{d}")
    d_ok = (after.frames_ok - before.frames_ok) & 0xFFFF
    rep.check(d_ok == 1, "STATUS.frames_ok +1 (yalnızca son HEARTBEAT)", f"+{d_ok}")

    # HELLO_REQ seli: saniyede en fazla 2 cevap. Art arda 5 istek → 1 HELLO
    link.receive(0.6)   # son HELLO'dan beri 500 ms geçsin
    req = fr.encode_frame(fr.Frame(m.HelloReq.ID, 0, 0, b""), link.key, 0)
    for _ in range(5):
        link.write(req)
    hellos = [m.Hello.unpack(f.payload) for f, c in link.receive(1.0) if c is m.Hello]
    rep.check(len(hellos) == 1, "5 HELLO_REQ → 1 HELLO", f"{len(hellos)} HELLO")
    if hellos:
        rep.check(hellos[0].last_rx_seq == link.seq, "HELLO.last_rx_seq son kabul edilen sayaç",
                  f"{hellos[0].last_rx_seq} (gönderilen son geçerli sayaç {link.seq})")
    return hello.session_id


def test_vehicle(link: Link, agent_session: int, rep: Report) -> None:
    print("Araç kanalı")
    hello, how = link.connect()
    rep.check(True, f"HELLO geldi ({how})")
    rep.check(hello.session_id == agent_session, "oturum kimliği ajan kanalıyla aynı")

    before = link.status()
    link.send(m.Telemetry(-45, 812, -3000))
    no_reply(link, "TELEMETRY (cevap beklenmiyor)", rep)
    link.send(m.Heartbeat(7))   # HEARTBEAT yalnızca ajan kanalına ait
    no_reply(link, "HEARTBEAT araç kanalından", rep)
    after = link.status()
    d_ok = (after.frames_ok - before.frames_ok) & 0xFFFF
    d_type = (after.err_type - before.err_type) & 0xFFFF
    rep.check(d_ok == 1, "STATUS.frames_ok +1 (TELEMETRY)", f"+{d_ok}")
    rep.check(d_type == 1, "STATUS.err_type +1 (HEARTBEAT)", f"+{d_type}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=AGENT_PORT, help="ajan kanalı")
    ap.add_argument("--vehicle-port", default=VEHICLE_PORT, help="araç kanalı")
    ap.add_argument("--no-vehicle", action="store_true", help="araç kanalını atla")
    args = ap.parse_args()

    if not KEY_FILE.exists():
        print(f"{KEY_FILE.relative_to(ROOT)} yok. Önce: python3 tools/gen_key.py", file=sys.stderr)
        return 2
    key = KEY_FILE.read_bytes()

    rep = Report()
    try:
        agent_session = test_agent(Link(args.port, m.Channel.AGENT, key), rep)
        if not args.no_vehicle:
            test_vehicle(Link(args.vehicle_port, m.Channel.VEHICLE, key), agent_session, rep)
    except (RuntimeError, fr.FrameError, serial.SerialException) as e:
        print(f"  [KALDI] {e}")
        rep.failed += 1

    print("SONUÇ: " + ("hepsi geçti" if rep.failed == 0 else f"{rep.failed} denetim kaldı"))
    return 0 if rep.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
