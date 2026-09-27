#!/usr/bin/env python3
"""Ajan kanalı yankı testi (Faz 2.2).

Kullanım:
    python3 tools/echo_test.py                        # 100 KB, kalıcı port adı
    python3 tools/echo_test.py --bytes 1000 --port /dev/ttyACM0

Karttaki yankı programı (firmware/app/app.c) aldığı her baytı geri gönderir.
Bu betik karta rastgele baytlar gönderir ve geri geleni gönderdiğiyle bayt
bayt karşılaştırır. Böylece taşıma katmanı (USB, ST-LINK, LPUART1, DMA,
dairesel tampon) protokol gelmeden, tek başına doğrulanır.

Önce minicom gibi aynı portu açan programları kapatın. İki program aynı portu
okursa baytları aralarında bölüşür ve test sahte kayıp gösterir.
"""
from __future__ import annotations

import argparse
import random
import sys
import time

import serial

DEFAULT_PORT = (
    "/dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_003B00163235511037333439-if02"
)
BAUD = 115200
# 8N1'de her bayt hatta 10 bit: başlangıç + 8 veri + durma.
LINE_LIMIT = BAUD // 10

# Yolda (gönderilmiş ama henüz geri gelmemiş) en fazla bu kadar bayt olur.
# Yankıda kart aldığından hızlı gönderemez. PC'nin saati kartınkinden biraz
# bile hızlıysa fark birikir ve karttaki 256 baytlık dairesel tampon taşar.
# Bu sınır buna izin vermez.
WINDOW = 128

# Bu kadar süre hiç bayt gelmezse kart cevap vermiyor sayılır.
TIMEOUT_S = 1.0


def run(port: str, n: int, seed: int) -> int:
    # Sabit tohum: her koşu aynı baytları gönderir. 0x00 dahil her değer geçer.
    data = random.Random(seed).randbytes(n)
    received = bytearray()
    sent = 0

    with serial.Serial(port, BAUD, timeout=0.01) as ser:
        ser.reset_input_buffer()  # Önceki oturumdan kalan baytlar karışmasın
        start = time.monotonic()
        last_rx = start
        while len(received) < n:
            room = WINDOW - max(sent - len(received), 0)
            if sent < n and room > 0:
                sent += ser.write(data[sent : sent + min(room, n - sent)])
            got = ser.read(ser.in_waiting or 1)
            if got:
                received += got
                last_rx = time.monotonic()
            elif time.monotonic() - last_rx > TIMEOUT_S:
                break
        elapsed = time.monotonic() - start

    # Bir bayt kaybolursa ondan sonraki her bayt kayar ve "farklı" sayılır.
    # Asıl bilgi ilk farkın yeri.
    diffs = [i for i, (a, b) in enumerate(zip(data, received)) if a != b]
    rate = len(received) / elapsed if elapsed > 0 else 0.0
    print(
        f"gönderilen {sent} · alınan {len(received)} · farklı {len(diffs)} · "
        f"süre {elapsed:.1f} s · {rate:.0f} B/s (hat üst sınırı {LINE_LIMIT} B/s)"
    )
    if diffs:
        i = diffs[0]
        print(f"ilk fark: bayt {i}, beklenen 0x{data[i]:02x}, gelen 0x{received[i]:02x}")
    if len(received) < n:
        print(f"zaman aşımı: {TIMEOUT_S} s boyunca bayt gelmedi")
    elif len(received) > n:
        print(f"fazladan {len(received) - n} bayt geldi")

    ok = bytes(received) == data
    print("GEÇTİ" if ok else "KALDI")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--port", default=DEFAULT_PORT, help="seri port (varsayılan: ajan kanalının kalıcı adı)")
    ap.add_argument("--bytes", type=int, default=100 * 1024, help="gönderilecek bayt sayısı")
    ap.add_argument("--seed", type=int, default=0, help="rastgele veri tohumu")
    args = ap.parse_args()

    try:
        return run(args.port, args.bytes, args.seed)
    except serial.SerialException as e:
        print(f"port açılamadı: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
