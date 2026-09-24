"""Çerçeve katmanı: referans uygulama (docs/protocol.md §4).

Mesaj tanımı değil, çerçeveleme algoritmasıdır. Bu yüzden elle yazılır.
Sabitlerin hepsi messages.py'den, dolayısıyla messages.yaml'dan gelir.

Kartın C uygulaması (firmware/app/protocol/) shared/protocol/test_vectors.json'
daki baytları birebir üretmeli ve kötü çerçeveleri aynı türle reddetmelidir.

Bu katman durumsuzdur. Sayaç (REPLAY) ve tazelik (FRESHNESS) alıcının durumuna
bağlı olduğu için burada değil, alıcıda denetlenir.
"""
from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass
from typing import List, Tuple, Type, Union

from ika_protocol import messages as m


class FrameError(Exception):
    """Çerçeve reddi. `kind`, kartın STATUS sayaçlarıyla birebir eşleşir:

    framing  COBS hatası, çok kısa ya da tamponu taşan çerçeve   → err_framing
    crc      CRC tutmuyor                                          → err_crc
    type     bilinmeyen tip, yanlış kanal/yön ya da yanlış uzunluk → err_type
    auth     HMAC etiketi tutmuyor (yanlış anahtar ya da oturum)   → err_auth
    """

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True)
class Frame:
    type: int
    seq: int
    ts_ms: int
    payload: bytes


# --------------------------------------------------------------------------
#  CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, yansıtmasız, xorout 0.
#  Bilinen cevap: "123456789" → 0x29B1
# --------------------------------------------------------------------------

def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


# --------------------------------------------------------------------------
#  COBS. Kodlanmış veride 0x00 hiç geçmez, bu yüzden 0x00 çerçeve ayracıdır.
#  Kanonik biçim: veri tam 254 sıfırsız baytlık bir blokla biterse sona ek
#  kod baytı konmaz (Cheshire & Baker; Wikipedia örnekleriyle aynı).
# --------------------------------------------------------------------------

def cobs_encode(data: bytes) -> bytes:
    out = bytearray()
    block = bytearray()
    last = len(data) - 1
    for i, byte in enumerate(data):
        if byte == 0:
            out.append(len(block) + 1)
            out += block
            block.clear()
        else:
            block.append(byte)
            if len(block) == 254:
                out.append(0xFF)
                out += block
                block.clear()
                if i == last:
                    return bytes(out)
    out.append(len(block) + 1)
    out += block
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    if not data:
        raise FrameError("framing", "boş çerçeve")
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        code = data[i]
        if code == 0:
            raise FrameError("framing", f"{i}. baytta 0x00")
        i += 1
        end = i + code - 1
        if end > n:
            raise FrameError("framing", "COBS kodu çerçeve sonunun ötesini gösteriyor")
        block = data[i:end]
        if 0 in block:
            raise FrameError("framing", "blok içinde 0x00")
        out += block
        i = end
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)


# --------------------------------------------------------------------------
#  HMAC-SHA256, TAG_BYTES'a kısaltılmış.
#  Girdi = session_id (u32, LE) ‖ başlık ‖ yük.
#  Oturum kimliği gönderilmez ama imzaya girer: kart yeniden başlayınca eski
#  oturumun çerçeveleri AUTH ile düşer (docs/protocol.md §5).
# --------------------------------------------------------------------------

def compute_tag(key: bytes, session_id: int, header_and_payload: bytes) -> bytes:
    msg = struct.pack("<I", session_id) + header_and_payload
    return hmac.new(key, msg, hashlib.sha256).digest()[:m.TAG_BYTES]


# --------------------------------------------------------------------------
#  Çerçeve: COBS( başlık ‖ yük ‖ etiket ‖ CRC ) ‖ 0x00
# --------------------------------------------------------------------------

def encode_frame(frame: Frame, key: bytes, session_id: int) -> bytes:
    """Hattaki baytları döndürür (sondaki 0x00 ayracı dahil)."""
    cls = m.MESSAGES_BY_ID[frame.type]
    if len(frame.payload) != cls.SIZE:
        raise ValueError(f"{cls.NAME}: yük {len(frame.payload)} bayt, {cls.SIZE} olmalı")
    body = struct.pack(m.HEADER_FORMAT, frame.type, frame.seq, frame.ts_ms) + frame.payload
    # İmzasız mesajlarda (HELLO_REQ) etiket alanı yine vardır, sıfırlarla doldurulur
    tag = compute_tag(key, session_id, body) if cls.AUTH else bytes(m.TAG_BYTES)
    raw = body + tag
    raw += struct.pack("<H", crc16_ccitt_false(raw))
    return cobs_encode(raw) + bytes([m.FRAME_DELIMITER])


def decode_frame(data: bytes, *, key: bytes, session_id: int,
                 channel: m.Channel, direction: m.Direction) -> Tuple[Frame, Type]:
    """Ayraçsız kodlanmış çerçeveyi çözer ve denetler.

    Sıra docs/RULES.md §4 ile aynıdır: çerçeve → CRC → tip/kanal/yön/uzunluk → AUTH.
    `channel` ve `direction`, ALICININ bulunduğu port ve beklediği yöndür.
    """
    raw = cobs_decode(data)
    if len(raw) < m.HEADER_BYTES + m.TAG_BYTES + m.CRC_BYTES:
        raise FrameError("framing", f"{len(raw)} bayt, çok kısa")

    body_and_tag, crc_bytes = raw[:-m.CRC_BYTES], raw[-m.CRC_BYTES:]
    if crc16_ccitt_false(body_and_tag) != struct.unpack("<H", crc_bytes)[0]:
        raise FrameError("crc", "CRC tutmuyor")

    body, tag = body_and_tag[:-m.TAG_BYTES], body_and_tag[-m.TAG_BYTES:]
    type_id, seq, ts_ms = struct.unpack_from(m.HEADER_FORMAT, body)
    cls = m.MESSAGES_BY_ID.get(type_id)
    if cls is None:
        raise FrameError("type", f"bilinmeyen tip 0x{type_id:02X}")
    if cls.DIRECTION != direction:
        raise FrameError("type", f"{cls.NAME} bu yönde gelemez")
    if cls.CHANNEL not in (channel, m.Channel.BOTH):
        raise FrameError("type", f"{cls.NAME} {channel.name} kanalına ait değil")
    payload = body[m.HEADER_BYTES:]
    if len(payload) != cls.SIZE:
        raise FrameError("type", f"{cls.NAME} yükü {len(payload)} bayt, {cls.SIZE} olmalı")

    if cls.AUTH and not hmac.compare_digest(tag, compute_tag(key, session_id, body)):
        raise FrameError("auth", "HMAC etiketi tutmuyor")

    return Frame(type_id, seq, ts_ms, payload), cls


class StreamDecoder:
    """Seri porttan gelen bayt akışını ayraçlarda böler.

    feed() tamamlanan her çerçeveyi (ayraçsız bayt olarak) ya da taşma durumunda
    FrameError("framing") döndürür. Art arda iki ayraç (boş çerçeve) yok sayılır.
    Göndericiler hat senkronunu tazelemek için çerçeve başına ayraç koyabilir.
    """

    def __init__(self, max_wire_bytes: int = m.MAX_WIRE_BYTES) -> None:
        self._max = max_wire_bytes
        self._buf = bytearray()
        self._overflow = False

    def feed(self, data: bytes) -> List[Union[bytes, FrameError]]:
        out: List[Union[bytes, FrameError]] = []
        for byte in data:
            if byte == m.FRAME_DELIMITER:
                if self._overflow:
                    out.append(FrameError("framing", f"{self._max} baytı aşan çerçeve"))
                elif self._buf:
                    out.append(bytes(self._buf))
                self._buf.clear()
                self._overflow = False
            elif not self._overflow:
                self._buf.append(byte)
                if len(self._buf) >= self._max:   # ayraçla birlikte sınırı aşar
                    self._overflow = True
                    self._buf.clear()
        return out
