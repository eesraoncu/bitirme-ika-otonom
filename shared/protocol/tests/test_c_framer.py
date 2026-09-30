"""Kartın çerçeveleme kodu (firmware/app/protocol/) Python referansıyla aynı mı.

    python3 -m pytest shared/protocol/tests -v

c_driver.c, kartın C kaynaklarıyla birlikte gcc ile derlenir. Testler sürücüye
komut yollar ve cevabı hem test_vectors.json'la hem frame.py ile karşılaştırır.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[3]
PROTO = ROOT / "shared" / "protocol"
APP = ROOT / "firmware" / "app"
sys.path.insert(0, str(PROTO / "python"))

from ika_protocol import frame as fr   # noqa: E402

VECTORS = json.loads((PROTO / "test_vectors.json").read_text(encoding="utf-8"))
C_SOURCES = [APP / "protocol" / "crc16.c", APP / "protocol" / "cobs.c"]

pytestmark = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc yok")


@pytest.fixture(scope="module")
def driver(tmp_path_factory):
    exe = tmp_path_factory.mktemp("c") / "driver"
    cc = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wsign-conversion",
         "-Werror", "-I", str(APP), str(PROTO / "tests" / "c_driver.c"),
         *map(str, C_SOURCES), "-o", str(exe)],
        capture_output=True, text=True)
    assert cc.returncode == 0, "Kartın C kodu katı uyarılarla derlenmedi:\n" + cc.stderr

    def run(commands: List[str]) -> List[str]:
        r = subprocess.run([str(exe)], input="\n".join(commands) + "\n",
                           capture_output=True, text=True)
        assert r.returncode == 0
        out = r.stdout.splitlines()
        assert len(out) == len(commands)
        return out

    return run


def _cmd(name: str, data: bytes) -> str:
    return f"{name} {data.hex()}" if data else name


# ---- test_vectors.json -------------------------------------------------------

def test_crc_known_answer(driver):
    for vec in VECTORS["crc16_ccitt_false"]:
        data = bytes.fromhex(vec["input_hex"])
        assert int(driver([_cmd("crc", data)])[0], 16) == int(vec["crc"], 16)


@pytest.mark.parametrize("vec", VECTORS["cobs"], ids=lambda v: v["decoded_hex"][:16] or "bos")
def test_cobs_vectors(driver, vec):
    decoded = bytes.fromhex(vec["decoded_hex"])
    encoded = bytes.fromhex(vec["encoded_hex"])
    enc, dec = driver([_cmd("cobs_enc", decoded), _cmd("cobs_dec", encoded)])
    assert enc == encoded.hex()
    assert dec == decoded.hex()


# ---- Bozuk COBS reddedilmeli ---------------------------------------------------

@pytest.mark.parametrize("bad, why", [
    ("", "boş çerçeve"),
    ("00", "kod baytı 0x00"),
    ("031100", "blok içinde 0x00"),
    ("0511", "kod çerçeve sonunun ötesini gösteriyor"),
    ("0311220233" + "00", "sonda ayraç kalmış"),
])
def test_cobs_rejects_bad(driver, bad, why):
    data = bytes.fromhex(bad)
    with pytest.raises(fr.FrameError):
        fr.cobs_decode(data)                       # Python da reddediyor mu
    assert driver([_cmd("cobs_dec", data)]) == ["ERR"], why


@pytest.mark.parametrize("encoded, expect", [
    ("0511223344", "11223344"),     # tam 4 bayt: sığar
    ("0311220233", "11220033"),     # araya konan sıfırla 4 bayt: sığar
    ("061122334455", "ERR"),        # blok 5 bayt
    ("051122334401", "ERR"),        # blok 4 bayt, sonra araya konacak sıfır sığmıyor
])
def test_cobs_decode_respects_output_size(driver, encoded, expect):
    assert driver([_cmd("cobs_dec4", bytes.fromhex(encoded))]) == [expect]


# ---- Rastgele girdide C ile Python aynı ----------------------------------------

def _random_data(rng: random.Random) -> bytes:
    n = rng.choice([rng.randrange(0, 50), rng.randrange(250, 600)])
    zero_rate = rng.choice([0.0, 0.05, 0.3, 0.9])
    return bytes(0 if rng.random() < zero_rate else rng.randrange(1, 256) for _ in range(n))


def test_c_matches_python_on_random_data(driver):
    rng = random.Random(2026)
    cases = [_random_data(rng) for _ in range(300)]
    cmds = []
    for d in cases:
        cmds += [_cmd("crc", d), _cmd("cobs_enc", d), _cmd("cobs_dec", fr.cobs_encode(d))]
    out = driver(cmds)
    for i, d in enumerate(cases):
        crc, enc, dec = out[3 * i: 3 * i + 3]
        assert int(crc, 16) == fr.crc16_ccitt_false(d)
        assert enc == fr.cobs_encode(d).hex()
        assert dec == d.hex()


def _damaged_encoding(rng: random.Random) -> bytes:
    """Geçerli bir kodlamanın bir baytını boz ya da sonunu kes. Bir kısmı yine
    çözülebilir kalır, bir kısmı reddedilir: iki yol da sınanır."""
    e = bytearray(fr.cobs_encode(_random_data(rng)))
    if rng.random() < 0.5:
        e[rng.randrange(len(e))] = rng.choice([0, rng.randrange(1, 256)])
    else:
        del e[rng.randrange(1, len(e) + 1):]
    return bytes(e)


def test_c_matches_python_on_damaged_encodings(driver):
    """Bozuk kodlamada ikisi de ya aynı sonucu verir ya da ikisi de reddeder."""
    rng = random.Random(2027)
    cases = [_damaged_encoding(rng) for _ in range(500)]
    out = driver([_cmd("cobs_dec", d) for d in cases])
    rejected = out.count("ERR")
    assert 50 < rejected < 450, f"{rejected}/500 reddedildi: iki yol da sınanmalı"
    for d, got in zip(cases, out):
        try:
            expect = fr.cobs_decode(d).hex()
        except fr.FrameError:
            expect = "ERR"
        assert got == expect, d.hex()
