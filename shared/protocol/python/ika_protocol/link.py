"""Kartla bir kanal üzerinden konuşan uç: oturum, imza, sayaç, akış senkronu.

Testler (tools/link_test.py, decision_test.py, unplug_test.py) ve köprü
(ros2_ws/src/guard_bridge) aynı kodu kullanır (K-040). Bir kanal bir Link'tir.
Çerçeve biçimi frame.py'de, mesajlar messages.py'de (messages.yaml'dan üretilir).
"""
from __future__ import annotations

import struct
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import serial

from . import frame as fr
from . import messages as m

ROOT = Path(__file__).resolve().parents[4]   # depo kökü
AGENT_PORT = "/dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_003B00163235511037333439-if02"
VEHICLE_PORT = ("/dev/serial/by-id/"
                "usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0")
KEY_FILE = ROOT / "secrets" / "hmac_key.bin"   # depoya girmez (CLAUDE.md)

HELLO_BROADCAST_WAIT_S = 1.2   # kart oturum kurulana kadar 500 ms'de bir yayınlar
REPLY_WAIT_S = 0.3             # cevap beklenen ya da beklenmeyen süre
STATUS_WAIT_S = 2.5            # STATUS saniyede bir


class Link:
    """Bir kanala köprü gibi bağlanan uç."""

    def __init__(self, port: str, channel: m.Channel, key: bytes, *, strict: bool = True) -> None:
        # Akış kontrolü kapalı: açıkken baytlar CP2102'de bekleyip karta
        # ulaşmıyordu (docs/STATUS.md, Faz 2.5).
        self.ser = serial.Serial(port, 115200, timeout=0.02, rtscts=False)
        self.ser.reset_input_buffer()
        self.channel = channel
        self.key = key
        # strict: ilk geçerli çerçeveden sonraki bozuk çerçeve hata yükseltir
        # (testler). False: sayılır ve geçilir (köprü, docs/protocol.md §10).
        self.strict = strict
        self.rx_errors = 0
        self.decoder = fr.StreamDecoder()
        self.pending: List[Tuple[fr.Frame, type]] = []   # okunmuş, henüz bakılmamış
        self.synced = False   # ilk ayraç görüldü mü
        self.clean = False    # ilk geçerli çerçeve görüldü mü
        # Kalp atışı başka bir iş parçacığından gönderilebilir (decision_test.py)
        self.lock = threading.Lock()
        self.session_id: Optional[int] = None
        self.seq = 0
        self.board_ms_at: Tuple[int, float] = (0, time.monotonic())

    # -- alma ------------------------------------------------------------

    def _decode(self, data: bytes) -> Optional[Tuple[fr.Frame, type]]:
        """Karttan gelen çerçeveyi çözer. HELLO, içindeki oturum kimliğiyle
        doğrulanır (docs/protocol.md §5.3). Oturum kimliği öğrenilmeden gelen
        başka çerçeveler doğrulanamaz, atlanır (None). Doğrulanamayan her
        diğer çerçeve hatadır."""
        sid = self.session_id
        raw = fr.cobs_decode(data)
        if raw[0] == m.Hello.ID:
            sid = struct.unpack_from("<I", raw, m.HEADER_BYTES)[0]
        elif sid is None:
            return None
        f, cls = fr.decode_frame(data, key=self.key, session_id=sid,
                                 channel=self.channel, direction=m.Direction.BOARD_TO_PC)
        return f, cls

    def _next(self, end: float) -> Optional[Tuple[fr.Frame, type]]:
        """Sıradaki çerçeve. Bir okumada birden fazla çerçeve gelebilir:
        bakılmayanlar pending'de kalır, kaybolmaz."""
        while not self.pending and time.monotonic() < end:
            data = self.ser.read(256)
            if not self.synced:
                # Kart sürekli gönderiyor. Port bir çerçevenin ortasında
                # açılmış olabilir: ilk ayraca kadar gelen yarım çerçeve atılır.
                i = data.find(bytes([m.FRAME_DELIMITER]))
                if i < 0:
                    continue
                data = data[i + 1:]
                self.synced = True
            for item in self.decoder.feed(data):
                try:
                    if isinstance(item, fr.FrameError):
                        raise item
                    got = self._decode(item)
                except fr.FrameError:
                    # Kart yeniden başlarken gönderdiği çerçeve yarıda kalır;
                    # USB köprüsü o baytları tutup port açılınca verir. İlk
                    # geçerli çerçeveden önceki bozukluk bunun izidir, sonraki
                    # her bozukluk gerçek bir hatadır.
                    if self.clean:
                        if self.strict:
                            raise
                        self.rx_errors += 1
                    continue
                if got is not None:
                    # "Geçerli" = imzası ve CRC'si doğrulanmış. Oturum kimliği
                    # öğrenilmeden atlanan çerçeve (None) doğrulanmadı: USB'de
                    # bekleyen eski baytlar olabilir, ardından gelen bozukluk
                    # hâlâ açılışın izidir.
                    self.clean = True
                    self.pending.append(got)
        return self.pending.pop(0) if self.pending else None

    def receive(self, seconds: float) -> List[Tuple[fr.Frame, type]]:
        """seconds boyunca gelen bütün çerçeveler."""
        out = []
        end = time.monotonic() + seconds
        while (got := self._next(end)) is not None:
            out.append(got)
        return out

    def wait_for(self, cls: type, seconds: float,
                 match: Callable[[object], bool] = lambda _: True):
        """cls türünden ilk uygun mesajı döndürür, gelmezse None. Öncekiler atılır."""
        end = time.monotonic() + seconds
        while (got := self._next(end)) is not None:
            f, c = got
            if c is cls:
                msg = c.unpack(f.payload)
                if match(msg):
                    return f, msg
        return None

    # -- gönderme ----------------------------------------------------------

    def board_now(self) -> int:
        """Kartın saatinin tahmini. ts_ms kartın saat alanındadır (§6.3).
        Tazelik henüz denetlenmiyor (Faz 4), yine de doğru alan kullanılır."""
        ms, at = self.board_ms_at
        return (ms + int((time.monotonic() - at) * 1000)) & 0xFFFFFFFF

    def frame(self, msg, *, seq: Optional[int] = None) -> fr.Frame:
        if seq is None:
            with self.lock:
                self.seq += 1
                seq = self.seq
        return fr.Frame(msg.ID, seq, self.board_now(), msg.pack())

    def encode(self, f: fr.Frame, *, key: Optional[bytes] = None,
               session_id: Optional[int] = None) -> bytes:
        return fr.encode_frame(f, key or self.key,
                               self.session_id if session_id is None else session_id)

    def write(self, wire: bytes) -> None:
        with self.lock:
            self.ser.write(wire)
            self.ser.flush()

    def send(self, msg) -> bytes:
        # Sayaç ve yazma tek kilitte: iki iş parçacığı çerçeveleri sayaç
        # sırasının tersine yazarsa kart küçük sayaçlıyı REPLAY ile düşürür.
        with self.lock:
            wire = self.encode(self.frame_locked(msg))
            self.ser.write(wire)
            self.ser.flush()
        return wire

    def frame_locked(self, msg) -> fr.Frame:
        self.seq += 1
        return fr.Frame(msg.ID, self.seq, self.board_now(), msg.pack())

    # -- oturum --------------------------------------------------------------

    def connect(self) -> Tuple[m.Hello, str]:
        got = self.wait_for(m.Hello, HELLO_BROADCAST_WAIT_S)
        how = "yayından"
        if got is None:
            self.write(fr.encode_frame(fr.Frame(m.HelloReq.ID, 0, 0, b""), self.key, 0))
            got = self.wait_for(m.Hello, REPLY_WAIT_S + 0.5)
            how = "HELLO_REQ cevabı"
        if got is None:
            raise RuntimeError("HELLO gelmedi")
        f, hello = got
        self.session_id = hello.session_id
        self.seq = hello.last_rx_seq   # köprü bir fazlasından devam eder
        self.board_ms_at = (f.ts_ms, time.monotonic())
        return hello, how

    def status(self) -> m.Status:
        got = self.wait_for(m.Status, STATUS_WAIT_S)
        if got is None:
            raise RuntimeError("STATUS gelmedi")
        return got[1]


# --------------------------------------------------------------------------


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
