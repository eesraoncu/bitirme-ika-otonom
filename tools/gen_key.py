#!/usr/bin/env python3
"""HMAC anahtarı: secrets/hmac_key.bin ve kart için secrets/hmac_key.h.

Kullanım:
    python3 tools/gen_key.py

Anahtar yoksa işletim sisteminin güvenli rastgele kaynağından (os.urandom)
32 bayt üretilir. Varsa ÜZERİNE YAZILMAZ: yazılsaydı kart ile bilgisayar
habersizce farklı anahtarlara düşer, her çerçeve err_auth ile reddedilirdi.
Anahtarı değiştirmek için dosya elle silinir, betik yeniden çalıştırılır ve
kart yeniden derlenip yüklenir.

C başlığı her çalıştırmada .bin'den yeniden yazılır. CubeIDE derlerken betik
çalıştırmadığı için başlık derlemeden önce burada üretilir. İkisi de
secrets/ altında ve depoya girmez (K-007, docs/protocol.md §11).

Betik anahtarı ekrana yazmaz. İki tarafın aynı anahtarı bildiği "parmak izi"
ile denetlenir: herkesin bildiği sabit bir mesajın HMAC'i. HMAC'ten anahtar
geri çıkarılamaz, bu yüzden parmak izi gizli değildir.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"
KEY_BIN = SECRETS / "hmac_key.bin"
KEY_H = SECRETS / "hmac_key.h"
KEY_BYTES = 32

# Kartta aynı mesaj firmware/app/app.c'de (geçici anahtar denetimi).
FINGERPRINT_MSG = b"IKA anahtar denetimi"
FINGERPRINT_BYTES = 8

TEST_KEY = bytes(range(32))   # test_vectors.json'daki anahtar


def create_key() -> bytes:
    key = os.urandom(KEY_BYTES)
    SECRETS.mkdir(mode=0o700, exist_ok=True)
    # O_EXCL: dosya bu arada oluşmuşsa üzerine yazmak yerine hata ver.
    # 0o600: yalnızca dosyanın sahibi okuyabilsin.
    fd = os.open(KEY_BIN, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def load_key() -> bytes:
    key = KEY_BIN.read_bytes()
    if len(key) != KEY_BYTES:
        raise ValueError(f"{KEY_BIN.relative_to(ROOT)} {len(key)} bayt, {KEY_BYTES} olmalı")
    if key == TEST_KEY:
        raise ValueError("test anahtarı gerçek anahtar olarak kullanılamaz")
    return key


def render_header(key: bytes) -> str:
    rows = []
    for i in range(0, len(key), 8):
        rows.append("    " + ", ".join(f"0x{b:02X}" for b in key[i:i + 8]) + ",")
    return (
        "/* GİZLİ. DEPOYA GİRMEZ (K-007).\n"
        " * OTOMATİK ÜRETİLDİ. ELLE DÜZENLEMEYİN.\n"
        " * Kaynak: secrets/hmac_key.bin\n"
        " * Üretici: tools/gen_key.py */\n"
        "#ifndef HMAC_KEY_H\n"
        "#define HMAC_KEY_H\n"
        "\n"
        f"#define HMAC_KEY_LEN {len(key)}\n"
        "#define HMAC_KEY_INIT { \\\n"
        + " \\\n".join(rows) + " \\\n"
        "}\n"
        "\n"
        "#endif /* HMAC_KEY_H */\n"
    )


def fingerprint(key: bytes) -> bytes:
    return hmac.new(key, FINGERPRINT_MSG, hashlib.sha256).digest()[:FINGERPRINT_BYTES]


def main() -> int:
    if KEY_BIN.exists():
        try:
            key = load_key()
        except ValueError as e:
            print(f"hata: {e}", file=sys.stderr)
            return 1
        print(f"var olan anahtar kullanıldı: {KEY_BIN.relative_to(ROOT)}")
    else:
        key = create_key()
        print(f"yeni anahtar üretildi: {KEY_BIN.relative_to(ROOT)}")

    fd = os.open(KEY_H, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(render_header(key))
    print(f"yazıldı: {KEY_H.relative_to(ROOT)}")
    print(f"parmak izi: {fingerprint(key).hex(' ').upper()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
