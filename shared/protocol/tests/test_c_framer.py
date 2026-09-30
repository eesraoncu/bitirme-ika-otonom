"""Kartın çerçeveleme kodu (firmware/app/protocol/, firmware/app/auth/)
Python referansıyla aynı mı.

    python3 -m pytest shared/protocol/tests -v

c_driver.c, kartın C kaynaklarıyla birlikte gcc ile derlenir. Testler sürücüye
komut yollar ve cevabı hem test_vectors.json'la hem frame.py ile karşılaştırır.
"""
from __future__ import annotations

import hashlib
import hmac
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
C_SOURCES = [APP / "protocol" / "crc16.c", APP / "protocol" / "cobs.c",
             APP / "auth" / "sha256.c", APP / "auth" / "hmac_sha256.c"]

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


def _hex(data: bytes) -> str:
    return data.hex() if data else "-"


def _chunks(*parts: bytes) -> str:
    """Her parça sürücüde ayrı bir update çağrısıyla verilir."""
    return ".".join(p.hex() for p in parts) if any(parts) else "-"


def _cmd(name: str, data: bytes) -> str:
    return f"{name} {_hex(data)}"


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


# ---- SHA-256 -----------------------------------------------------------------
#  Girdiler NIST'in örnekleri (FIPS 180-4 ekleri). Beklenen değerler hashlib'den.

NIST_INPUTS = [
    b"abc",
    b"",
    b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
    b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmn"
    b"hijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
]


def test_sha256_abc_known_answer(driver):
    assert driver(["sha256 " + _hex(b"abc")]) == [
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"]


@pytest.mark.parametrize("data", NIST_INPUTS, ids=lambda d: f"{len(d)}B")
def test_sha256_nist_inputs(driver, data):
    assert driver(["sha256 " + _hex(data)]) == [hashlib.sha256(data).hexdigest()]


def test_sha256_million_a(driver):
    """1 000 000 × 'a': 15 625 blok, parçalar değişen boylarda verilir."""
    expect = hashlib.sha256(b"a" * 1_000_000).hexdigest()
    assert driver(["sha256_rep 61 1000000"]) == [expect]


def test_sha256_every_length_around_block_boundaries(driver):
    """0–130 bayt: doldurmanın tek bloğa sığdığı (≤55) ve sığmadığı (56–63)
    her durum, tam blok (64) ve iki blok."""
    rng = random.Random(1)
    cases = [bytes(rng.randrange(256) for _ in range(n)) for n in range(131)]
    out = driver(["sha256 " + _hex(d) for d in cases])
    assert out == [hashlib.sha256(d).hexdigest() for d in cases]


def _split(rng: random.Random, data: bytes) -> str:
    """Veriyi rastgele yerlerden 1–5 parçaya böler."""
    cuts = sorted(rng.randrange(len(data) + 1) for _ in range(rng.randrange(5)))
    edges = [0, *cuts, len(data)]
    return _chunks(*(data[a:b] for a, b in zip(edges, edges[1:])))


def test_sha256_random_splits(driver):
    rng = random.Random(3)
    cases = [bytes(rng.randrange(256) for _ in range(rng.randrange(300))) for _ in range(300)]
    out = driver(["sha256 " + _split(rng, d) for d in cases])
    assert out == [hashlib.sha256(d).hexdigest() for d in cases]


# ---- HMAC-SHA256 -------------------------------------------------------------
#  Girdiler RFC 4231'in örnekleri. Beklenen değerler Python'un hmac modülünden.

RFC4231 = [
    (b"\x0b" * 20, b"Hi There"),
    (b"Jefe", b"what do ya want for nothing?"),
    (b"\xaa" * 20, b"\xdd" * 50),
    (bytes(range(1, 26)), b"\xcd" * 50),
    (b"\x0c" * 20, b"Test With Truncation"),
    (b"\xaa" * 131, b"Test Using Larger Than Block-Size Key - Hash Key First"),
    (b"\xaa" * 131, b"This is a test using a larger than block-size key and a larger "
                    b"than block-size data. The key needs to be hashed before being "
                    b"used by the HMAC algorithm."),
]


@pytest.mark.parametrize("key, msg", RFC4231, ids=[f"case{i}" for i in range(1, 8)])
def test_hmac_rfc4231(driver, key, msg):
    expect = hmac.new(key, msg, hashlib.sha256).hexdigest()
    assert driver([f"hmac {_hex(key)} {_hex(msg)}"]) == [expect]


def test_hmac_protocol_example(driver):
    """docs/protocol.md §4.4: VELOCITY_CMD'nin etiketi 06 1A 85 7A 51 0A AA 4E.
    session_id ile başlık+yük, çerçevedeki gibi iki ayrı parça olarak verilir."""
    key = bytes.fromhex(VECTORS["test_key_hex"])
    raw = bytes.fromhex(VECTORS["example"]["raw_hex"])
    body, tag = raw[:-10], raw[-10:-2]
    session = VECTORS["session_id"].to_bytes(4, "little")
    out = driver([f"hmac {_hex(key)} {_chunks(session, body)}"])
    assert out[0][:16] == tag.hex() == "061a857a510aaa4e"


def test_hmac_random(driver):
    rng = random.Random(4)
    cases = []
    for _ in range(200):
        key = bytes(rng.randrange(256) for _ in range(rng.randrange(150)))
        msg = bytes(rng.randrange(256) for _ in range(rng.randrange(200)))
        cases.append((key, msg))
    out = driver([f"hmac {_hex(k)} {_split(rng, m)}" for k, m in cases])
    assert out == [hmac.new(k, m, hashlib.sha256).hexdigest() for k, m in cases]


# ---- Sabit zamanlı karşılaştırma ---------------------------------------------
#  Burada yalnızca doğru sonuç denetleniyor. Sürenin farka bağlı olmadığı
#  kartta DWT ile ölçülecek (Faz 2.6, kartlı kısım).

def test_tag_equal(driver):
    tag = bytes.fromhex("061a857a510aaa4e")
    cmds = [f"tag_eq {tag.hex()} {tag.hex()}"]
    for i in range(len(tag)):          # her konumda tek bit farkı
        bad = bytearray(tag)
        bad[i] ^= 0x01
        cmds.append(f"tag_eq {tag.hex()} {bad.hex()}")
    assert driver(cmds) == ["1"] + ["0"] * len(tag)
