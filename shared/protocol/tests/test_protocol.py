"""Protokol testleri.

    python3 -m pytest shared/protocol/tests -v

En önemlisi test_c_and_python_produce_identical_bytes: üretilen C başlığı
gcc ile derlenir ve her mesaj için Python'la AYNI baytları ürettiği doğrulanır.
Tek kaynak ilkesinin (K-003) kanıtı budur.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PROTO = ROOT / "shared" / "protocol"
sys.path.insert(0, str(PROTO / "python"))

from ika_protocol import frame as fr        # noqa: E402
from ika_protocol import messages as msgs   # noqa: E402

VECTORS = json.loads((PROTO / "test_vectors.json").read_text(encoding="utf-8"))
KEY = bytes.fromhex(VECTORS["test_key_hex"])
SESSION = VECTORS["session_id"]
ALL = list(msgs.MESSAGES_BY_ID.values())


def _receiver(cls):
    ch = msgs.Channel.AGENT if cls.CHANNEL in (msgs.Channel.AGENT, msgs.Channel.BOTH) else msgs.Channel.VEHICLE
    return {"channel": ch, "direction": cls.DIRECTION}


# ---- Üretilen dosyalar güncel mi ----------------------------------------------

def test_generated_files_are_up_to_date():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_protocol.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---- CRC ve COBS: bağımsız bilinen cevaplar -----------------------------------

def test_crc16_ccitt_false_known_answer():
    assert fr.crc16_ccitt_false(b"123456789") == 0x29B1


# Wikipedia "Consistent Overhead Byte Stuffing" örnekleri (ayraç hariç).
# Kendi kodlayıcımızdan değil, dışarıdan alındı: simetrik hataları yakalar.
WIKIPEDIA_COBS = [
    ("", "01"),
    ("00", "0101"),
    ("0000", "010101"),
    ("11220033", "0311220233"),
    ("11223344", "0511223344"),
    ("11000000", "0211010101"),
    (bytes(range(1, 255)).hex(), "ff" + bytes(range(1, 255)).hex()),
    ("00" + bytes(range(1, 255)).hex(), "01ff" + bytes(range(1, 255)).hex()),
    (bytes(range(1, 256)).hex(), "ff" + bytes(range(1, 255)).hex() + "02ff"),
]


@pytest.mark.parametrize("decoded,encoded", WIKIPEDIA_COBS)
def test_cobs_matches_wikipedia(decoded, encoded):
    assert fr.cobs_encode(bytes.fromhex(decoded)).hex() == encoded
    assert fr.cobs_decode(bytes.fromhex(encoded)).hex() == decoded


def test_cobs_roundtrip_random():
    rng = random.Random(1234)
    for _ in range(500):
        data = bytes(rng.choice([0, rng.randrange(256)]) for _ in range(rng.randrange(0, 600)))
        enc = fr.cobs_encode(data)
        assert 0 not in enc
        assert fr.cobs_decode(enc) == data


# ---- Mesajlar -----------------------------------------------------------------

def _extremes(cls):
    """Her alan için tipinin uç değerleri; enum alanlarında her değer."""
    import dataclasses
    import typing
    hints = typing.get_type_hints(cls)
    ranges = {"B": (0, 255), "H": (0, 65535), "I": (0, 2**32 - 1),
              "h": (-32768, 32767), "i": (-2**31, 2**31 - 1)}
    fields = dataclasses.fields(cls)
    fmt = cls.FORMAT[1:]
    cases = []
    for pick in (0, 1):
        vals = {}
        for f, ch in zip(fields, fmt):
            t = hints[f.name]
            if isinstance(t, type) and issubclass(t, msgs.IntEnum):
                members = list(t)
                vals[f.name] = members[0] if pick == 0 else members[-1]
            else:
                vals[f.name] = ranges[ch][pick]
        cases.append(cls(**vals))
    return cases


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.NAME)
def test_message_roundtrip_extremes(cls):
    for inst in _extremes(cls):
        data = inst.pack()
        assert len(data) == cls.SIZE
        assert cls.unpack(data) == inst


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.NAME)
def test_message_rejects_wrong_length(cls):
    with pytest.raises(ValueError):
        cls.unpack(bytes(cls.SIZE + 1))


def test_direction_is_encoded_in_top_bit():
    for cls in ALL:
        assert (cls.ID >= 0x80) == (cls.DIRECTION == msgs.Direction.BOARD_TO_PC), cls.NAME


def test_can_messages_fit_classic_can():
    for cls in ALL:
        if cls.CAN_ID is not None:
            assert cls.SIZE <= 8, cls.NAME
            assert cls.CHANNEL == msgs.Channel.VEHICLE, cls.NAME


def test_halt_wins_can_arbitration():
    """Küçük CAN kimliği tahkimi kazanır: durdurma komutu hiçbir zaman beklememeli."""
    can_ids = {cls.NAME: cls.CAN_ID for cls in ALL if cls.CAN_ID is not None}
    assert can_ids["HALT"] == min(can_ids.values())


def test_longest_frame_fits_receive_buffer():
    worst_raw = msgs.HEADER_BYTES + msgs.MAX_PAYLOAD_BYTES + msgs.TAG_BYTES + msgs.CRC_BYTES
    assert worst_raw + worst_raw // 254 + 1 + 1 <= msgs.MAX_WIRE_BYTES


# ---- Çerçeve -----------------------------------------------------------------

@pytest.mark.parametrize("vec", VECTORS["frames"], ids=lambda v: v["name"])
def test_frame_vectors_reproduce(vec):
    cls = msgs.MESSAGES_BY_NAME[vec["name"]]
    f = fr.Frame(cls.ID, vec["seq"], vec["ts_ms"], bytes.fromhex(vec["payload_hex"]))
    wire = fr.encode_frame(f, KEY, SESSION)
    assert wire.hex() == vec["wire_hex"]
    decoded, dcls = fr.decode_frame(wire[:-1], key=KEY, session_id=SESSION, **_receiver(cls))
    assert decoded == f and dcls is cls


@pytest.mark.parametrize("vec", VECTORS["bad_frames"], ids=lambda v: v["expect"] + ": " + v["desc"])
def test_bad_frames_rejected_with_expected_kind(vec):
    with pytest.raises(fr.FrameError) as e:
        fr.decode_frame(bytes.fromhex(vec["wire_hex"])[:-1], key=KEY, session_id=vec["session_id"],
                        channel=msgs.Channel[vec["receive_channel"].upper()],
                        direction=msgs.Direction[vec["receive_dir"].upper()])
    assert e.value.kind == vec["expect"]


def test_every_single_bit_flip_is_detected():
    """Örnek çerçevenin her bitini tek tek çevir: hiçbiri fark edilmeden geçmemeli."""
    raw = bytes.fromhex(VECTORS["example"]["raw_hex"])
    for i in range(len(raw) * 8):
        corrupted = bytearray(raw)
        corrupted[i // 8] ^= 1 << (i % 8)
        with pytest.raises(fr.FrameError):
            fr.decode_frame(fr.cobs_encode(bytes(corrupted)), key=KEY, session_id=SESSION,
                            channel=msgs.Channel.AGENT, direction=msgs.Direction.PC_TO_BOARD)


def test_wrong_key_is_auth_error():
    wire = bytes.fromhex(VECTORS["example"]["wire_hex"])
    with pytest.raises(fr.FrameError) as e:
        fr.decode_frame(wire[:-1], key=bytes(32), session_id=SESSION,
                        channel=msgs.Channel.AGENT, direction=msgs.Direction.PC_TO_BOARD)
    assert e.value.kind == "auth"


def test_reflected_frame_is_rejected():
    """Kartın gönderdiği bir çerçeve karta geri yollanırsa yön denetimi düşürür."""
    vec = next(v for v in VECTORS["frames"] if v["name"] == "VERDICT")
    with pytest.raises(fr.FrameError) as e:
        fr.decode_frame(bytes.fromhex(vec["wire_hex"])[:-1], key=KEY, session_id=SESSION,
                        channel=msgs.Channel.AGENT, direction=msgs.Direction.PC_TO_BOARD)
    assert e.value.kind == "type"


def test_hello_req_needs_no_key():
    """HELLO_REQ imzasızdır: köprü oturum kimliğini bilmeden de sorabilmeli."""
    f = fr.Frame(msgs.HelloReq.ID, 0, 0, b"")
    wire = fr.encode_frame(f, KEY, SESSION)
    decoded, _ = fr.decode_frame(wire[:-1], key=bytes(32), session_id=0,
                                 channel=msgs.Channel.VEHICLE, direction=msgs.Direction.PC_TO_BOARD)
    assert decoded == f


def test_stream_decoder_splits_resyncs_and_reports_overflow():
    a = bytes.fromhex(VECTORS["frames"][0]["wire_hex"])
    b = bytes.fromhex(VECTORS["frames"][1]["wire_hex"])
    dec = fr.StreamDecoder()
    # Başta ayraç (senkron tazeleme), iki çerçeve, bir baytlık parçalar hâlinde
    out = []
    for byte in b"\x00" + a + b:
        out += dec.feed(bytes([byte]))
    assert out == [a[:-1], b[:-1]]
    # Ayraçsız çöp tamponu taşırır: bir framing hatası, sonra toparlanır
    out = dec.feed(b"\x55" * 200 + b"\x00" + a)
    assert len(out) == 2
    assert isinstance(out[0], fr.FrameError) and out[0].kind == "framing"
    assert out[1] == a[:-1]


# ---- C ile Python aynı baytları üretiyor mu ------------------------------------

def _c_literal(value: int, ctype: str) -> str:
    if ctype.startswith("u"):
        return f"{value}u"
    return f"({ctype}_t)({value})" if value < 0 else str(value)


def _build_c_test() -> str:
    import dataclasses
    fmt_to_c = {"B": "u8", "H": "u16", "I": "u32", "h": "i16", "i": "i32"}
    ctypes = {"u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "i16": "int16", "i32": "int32"}
    L = ['#include <stdio.h>', '#include <string.h>', '#include "proto_msgs.h"', "",
         "static void hex(const char *name, const uint8_t *b, size_t n)", "{",
         '    printf("ENC %s ", name);',
         '    for (size_t i = 0; i < n; ++i) printf("%02x", (unsigned)b[i]);',
         '    printf("\\n");', "}", "", "int main(void)", "{", "    int fail = 0;",
         '    printf("HASH %08x\\n", (unsigned)PROTO_SCHEMA_HASH);']
    for vec in VECTORS["messages"]:
        cls = msgs.MESSAGES_BY_NAME[vec["name"]]
        name, low = cls.NAME, cls.NAME.lower()
        L.append(f"    if (proto_msg_info(PROTO_ID_{name}) == NULL || "
                 f"proto_msg_info(PROTO_ID_{name})->size != PROTO_SIZE_{name}) {{")
        L.append(f'        printf("INFO_FAIL {name}\\n"); fail = 1;')
        L.append("    }")
        fields = dataclasses.fields(cls)
        if not fields:
            continue
        kinds = [fmt_to_c[c] for c in cls.FORMAT[1:]]
        inits = ", ".join(f".{f.name} = {_c_literal(vec['fields'][f.name], ctypes[k])}"
                          for f, k in zip(fields, kinds))
        eq = " && ".join(f"d.{f.name} == m.{f.name}" for f in fields)
        L += ["    {",
              f"        proto_{low}_t m = {{{inits}}};",
              f"        proto_{low}_t d;",
              f"        uint8_t buf[PROTO_SIZE_{name}];",
              f"        proto_{low}_encode(&m, buf);",
              f'        hex("{name}", buf, sizeof buf);',
              f"        if (!proto_{low}_decode(buf, sizeof buf, &d) || !({eq})) {{",
              f'            printf("DECODE_FAIL {name}\\n"); fail = 1;',
              "        }",
              f"        if (proto_{low}_decode(buf, sizeof buf - 1u, &d)) {{",
              f'            printf("LEN_FAIL {name}\\n"); fail = 1;',
              "        }"]
        offset = 0
        for f, k in zip(fields, kinds):
            size = {"u8": 1, "u16": 2, "u32": 4, "i16": 2, "i32": 4}[k]
            enum_cls = getattr(msgs, str(f.type), None)
            if isinstance(enum_cls, type) and issubclass(enum_cls, msgs.IntEnum):
                L += ["        {",
                      "            uint8_t bad[sizeof buf];",
                      "            memcpy(bad, buf, sizeof buf);",
                      f"            bad[{offset}] = 0xEEu;",
                      f"            if (proto_{low}_decode(bad, sizeof bad, &d)) {{",
                      f'                printf("ENUM_FAIL {name}.{f.name}\\n"); fail = 1;',
                      "            }",
                      "        }"]
            offset += size
        L.append("    }")
    L += ["    if (proto_msg_info(0x7Eu) != NULL) {", '        printf("UNKNOWN_FAIL\\n"); fail = 1;', "    }",
          "    return fail;", "}"]
    return "\n".join(L) + "\n"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc yok")
def test_c_and_python_produce_identical_bytes(tmp_path):
    src = tmp_path / "t.c"
    exe = tmp_path / "t"
    src.write_text(_build_c_test(), encoding="utf-8")
    cc = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wsign-conversion",
         "-Werror", "-I", str(PROTO / "c"), str(src), "-o", str(exe)],
        capture_output=True, text=True)
    assert cc.returncode == 0, "Üretilen C başlığı katı uyarılarla derlenmedi:\n" + cc.stderr

    run = subprocess.run([str(exe)], capture_output=True, text=True)
    lines = run.stdout.splitlines()
    assert run.returncode == 0, "C tarafı iç denetimi başarısız:\n" + run.stdout

    assert lines[0] == f"HASH {msgs.SCHEMA_HASH:08x}"
    c_bytes = dict(line.split()[1:] for line in lines if line.startswith("ENC "))
    py_bytes = {v["name"]: v["payload_hex"] for v in VECTORS["messages"] if v["payload_hex"]}
    assert c_bytes == py_bytes
