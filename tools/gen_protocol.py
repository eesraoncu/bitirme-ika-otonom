#!/usr/bin/env python3
"""messages.yaml → C başlığı, Python modülü ve test vektörleri.

Kullanım:
    python3 tools/gen_protocol.py            # dosyaları üret
    python3 tools/gen_protocol.py --check    # üretilmiş dosyalar güncel mi?

K-003: mesaj formatı tek yerde tanımlanır. Bu betik o tek yerden iki tarafın
kodunu üretir. Üretilen dosyalar elle düzenlenmez; bir mesajı değiştirmek için
messages.yaml düzenlenir ve bu betik yeniden çalıştırılır.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "shared" / "protocol"
SOURCE = PROTO_DIR / "messages.yaml"
PY_PKG_DIR = PROTO_DIR / "python"
OUT_C = PROTO_DIR / "c" / "proto_msgs.h"
OUT_PY = PY_PKG_DIR / "ika_protocol" / "messages.py"
OUT_VECTORS = PROTO_DIR / "test_vectors.json"

# ad: (bayt, işaretli, struct karakteri, C tipi)
PRIMITIVES = {
    "u8": (1, False, "B", "uint8_t"),
    "u16": (2, False, "H", "uint16_t"),
    "u32": (4, False, "I", "uint32_t"),
    "i16": (2, True, "h", "int16_t"),
    "i32": (4, True, "i", "int32_t"),
}
CHANNELS = {"agent": 1, "vehicle": 2, "both": 3}
DIRECTIONS = {"pc_to_board": 0, "board_to_pc": 1}
EXPECTED_HEADER = [("type", "u8"), ("seq", "u32"), ("ts_ms", "u32")]
CAN_CLASSIC_MAX_PAYLOAD = 8
CAN_STD_ID_MAX = 0x7FF

# Test vektörleri için sabit anahtar ve oturum. GERÇEK ANAHTAR DEĞİLDİR.
TEST_KEY = bytes(range(32))
TEST_SESSION_ID = 0x1234ABCD

UPPER_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
LOWER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

GENERATED_NOTE = (
    "OTOMATİK ÜRETİLDİ. ELLE DÜZENLEMEYİN.\n"
    "Kaynak: shared/protocol/messages.yaml\n"
    "Üretici: tools/gen_protocol.py"
)


class SchemaError(Exception):
    pass


def _py_doc(text: str) -> str:
    """Belge metnini üretilen Python docstring'ine güvenle yerleştir."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _c_doc(text: str) -> str:
    """Belge metnini C yorumuna güvenle yerleştir."""
    return text.replace("*/", "* /")


@dataclass
class Field:
    name: str
    type: str
    enum: str | None = None
    unit: str | None = None
    doc: str | None = None

    @property
    def size(self) -> int:
        return PRIMITIVES[self.type][0]


@dataclass
class Message:
    name: str
    id: int
    channel: str
    dir: str
    auth: bool
    can_id: int | None
    doc: str
    fields: list[Field]

    @property
    def size(self) -> int:
        return sum(f.size for f in self.fields)

    @property
    def class_name(self) -> str:
        return "".join(part.capitalize() for part in self.name.split("_"))

    @property
    def c_name(self) -> str:
        return self.name.lower()

    @property
    def struct_format(self) -> str:
        return "<" + "".join(PRIMITIVES[f.type][2] for f in self.fields)


@dataclass
class Schema:
    version: int
    hash: int
    header: list[Field]
    tag_bytes: int
    max_wire_bytes: int
    enums: dict[str, dict[str, int]]
    enum_docs: dict[str, str]
    messages: list[Message]

    @property
    def header_bytes(self) -> int:
        return sum(f.size for f in self.header)

    @property
    def header_format(self) -> str:
        return "<" + "".join(PRIMITIVES[f.type][2] for f in self.header)

    @property
    def max_payload(self) -> int:
        return max(m.size for m in self.messages)

    @property
    def max_raw_bytes(self) -> int:
        return self.header_bytes + self.max_payload + self.tag_bytes + 2

    @property
    def max_encoded_bytes(self) -> int:
        # COBS: her 254 baytlık blok için 1 kod baytı, artı 1 ayraç
        return self.max_raw_bytes + self.max_raw_bytes // 254 + 1 + 1


# --------------------------------------------------------------------------
#  Yükleme ve doğrulama
# --------------------------------------------------------------------------

def _strip_docs(node):
    """Özet hesabı için 'doc' anahtarlarını at: belge düzenlemesi özeti değiştirmez."""
    if isinstance(node, dict):
        return {k: _strip_docs(v) for k, v in node.items() if k != "doc"}
    if isinstance(node, list):
        return [_strip_docs(v) for v in node]
    return node


def schema_hash(raw: dict) -> int:
    canonical = json.dumps(_strip_docs(copy.deepcopy(raw)), sort_keys=True,
                           ensure_ascii=False, separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(canonical.encode("utf-8")).digest()[:4], "big")


def _fits(value: int, type_name: str) -> bool:
    size, signed, _, _ = PRIMITIVES[type_name]
    bits = size * 8
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    return lo <= value <= hi


def _parse_field(spec: dict, where: str, enums: dict) -> Field:
    name, type_name = spec.get("name"), spec.get("type")
    if not isinstance(name, str) or not LOWER_NAME.match(name):
        raise SchemaError(f"{where}: geçersiz alan adı {name!r}")
    if type_name not in PRIMITIVES:
        raise SchemaError(f"{where}.{name}: bilinmeyen tip {type_name!r}")
    enum = spec.get("enum")
    if enum is not None:
        if enum not in enums:
            raise SchemaError(f"{where}.{name}: bilinmeyen enum {enum!r}")
        for vname, v in enums[enum].items():
            if not _fits(v, type_name):
                raise SchemaError(f"{where}.{name}: {enum}.{vname}={v} {type_name} tipine sığmıyor")
    return Field(name, type_name, enum, spec.get("unit"), spec.get("doc"))


def load_schema(path: Path = SOURCE) -> Schema:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    frame = raw["frame"]
    if frame.get("encoding") != "cobs" or frame.get("delimiter") != 0:
        raise SchemaError("frame: yalnızca COBS ve 0x00 ayracı destekleniyor")
    if frame.get("crc") != "crc16_ccitt_false":
        raise SchemaError("frame.crc: yalnızca crc16_ccitt_false destekleniyor")
    tag_bytes = frame["tag_bytes"]
    if not 4 <= tag_bytes <= 32:
        raise SchemaError("frame.tag_bytes 4..32 aralığında olmalı")

    # Enumlar (YAML 1.1'de ON/OFF/YES/NO bool olur; adlar str mi diye bakılır)
    enums: dict[str, dict[str, int]] = {}
    enum_docs: dict[str, str] = {}
    for ename, espec in raw.get("enums", {}).items():
        if not isinstance(ename, str) or not re.match(r"^[A-Z][A-Za-z0-9]*$", ename):
            raise SchemaError(f"enum adı geçersiz: {ename!r}")
        values = espec["values"]
        for vname, v in values.items():
            if not isinstance(vname, str) or not UPPER_NAME.match(vname):
                raise SchemaError(f"{ename}: geçersiz değer adı {vname!r} (YAML bool'a mı çevirdi?)")
            if not isinstance(v, int) or isinstance(v, bool):
                raise SchemaError(f"{ename}.{vname}: tamsayı olmalı")
        if len(set(values.values())) != len(values):
            raise SchemaError(f"{ename}: tekrarlanan değer")
        enums[ename] = dict(values)
        enum_docs[ename] = espec.get("doc", "")

    header = [_parse_field(f, "frame.header", enums) for f in frame["header"]]
    if [(f.name, f.type) for f in header] != EXPECTED_HEADER:
        raise SchemaError(f"frame.header tam olarak {EXPECTED_HEADER} olmalı")

    groups = {}
    for gname, gspec in raw.get("field_groups", {}).items():
        groups[gname] = gspec["fields"]

    messages: list[Message] = []
    seen_ids, seen_names, seen_can = set(), set(), set()
    for mspec in raw["messages"]:
        name = mspec["name"]
        if not UPPER_NAME.match(name) or name in seen_names:
            raise SchemaError(f"geçersiz ya da tekrarlanan mesaj adı: {name}")
        seen_names.add(name)

        mid = mspec["id"]
        if not isinstance(mid, int) or not 0 <= mid <= 0xFF or mid in seen_ids:
            raise SchemaError(f"{name}: geçersiz ya da tekrarlanan id {mid!r}")
        seen_ids.add(mid)

        channel, direction = mspec["channel"], mspec["dir"]
        if channel not in CHANNELS:
            raise SchemaError(f"{name}: bilinmeyen kanal {channel!r}")
        if direction not in DIRECTIONS:
            raise SchemaError(f"{name}: bilinmeyen yön {direction!r}")
        # Yön, kimliğin en üst bitinde: yansıtılan çerçeve tek bit testiyle reddedilir
        if (mid >= 0x80) != (direction == "board_to_pc"):
            raise SchemaError(f"{name}: board_to_pc kimlikleri ≥ 0x80, pc_to_board < 0x80 olmalı")

        auth = mspec.get("auth", True)
        if not isinstance(auth, bool):
            raise SchemaError(f"{name}.auth bool olmalı")

        fields: list[Field] = []
        for fspec in mspec.get("fields", []):
            if "group" in fspec:
                if fspec["group"] not in groups:
                    raise SchemaError(f"{name}: bilinmeyen alan grubu {fspec['group']!r}")
                fields += [_parse_field(g, name, enums) for g in groups[fspec["group"]]]
            else:
                fields.append(_parse_field(fspec, name, enums))
        if len({f.name for f in fields}) != len(fields):
            raise SchemaError(f"{name}: tekrarlanan alan adı")

        can_id = mspec.get("can_id")
        if can_id is not None:
            if channel != "vehicle":
                raise SchemaError(f"{name}: CAN'den yalnızca araç kanalı mesajları geçer")
            if not 0 <= can_id <= CAN_STD_ID_MAX or can_id in seen_can:
                raise SchemaError(f"{name}: geçersiz ya da tekrarlanan can_id {can_id!r}")
            seen_can.add(can_id)

        msg = Message(name, mid, channel, direction, auth, can_id,
                      " ".join(str(mspec.get("doc", "")).split()), fields)
        if can_id is not None and msg.size > CAN_CLASSIC_MAX_PAYLOAD:
            raise SchemaError(f"{name}: {msg.size} bayt, klasik CAN'e (8 bayt) sığmıyor")
        messages.append(msg)

    schema = Schema(raw["schema"]["version"], schema_hash(raw), header, tag_bytes,
                    frame["max_wire_bytes"], enums, enum_docs, messages)
    if schema.max_encoded_bytes > schema.max_wire_bytes:
        raise SchemaError(f"en uzun çerçeve {schema.max_encoded_bytes} bayt, "
                          f"max_wire_bytes={schema.max_wire_bytes} sınırını aşıyor")
    return schema


# --------------------------------------------------------------------------
#  C üretimi
# --------------------------------------------------------------------------

def _c_enum_prefix(ename: str) -> str:
    return "PROTO_" + re.sub(r"(?<!^)(?=[A-Z])", "_", ename).upper()


def render_c(s: Schema) -> str:
    L: list[str] = []
    w = L.append
    w("/*")
    for line in GENERATED_NOTE.splitlines():
        w(f" * {line}")
    w(" *")
    w(" * Mesaj tanımları, kodlayıcılar ve çözücüler. Çerçeveleme (COBS, CRC,")
    w(" * HMAC) burada değil, firmware/app/protocol/ altında elle yazılır ve")
    w(" * shared/protocol/test_vectors.json'daki baytları birebir üretmelidir.")
    w(" *")
    w(" * Tamsayılar little-endian. İşaretli çözmede (intN_t) dönüşümü GCC'nin")
    w(" * ikiye tümleyen davranışına dayanır.")
    w(" */")
    w("#ifndef PROTO_MSGS_H")
    w("#define PROTO_MSGS_H")
    w("")
    w("#include <stdbool.h>")
    w("#include <stddef.h>")
    w("#include <stdint.h>")
    w("")
    w(f"#define PROTO_SCHEMA_VERSION     {s.version}u")
    w(f"#define PROTO_SCHEMA_HASH        0x{s.hash:08X}u")
    w("#define PROTO_FRAME_DELIMITER    0x00u")
    w(f"#define PROTO_HEADER_BYTES       {s.header_bytes}u")
    w(f"#define PROTO_TAG_BYTES          {s.tag_bytes}u")
    w("#define PROTO_CRC_BYTES          2u")
    w(f"#define PROTO_MAX_PAYLOAD_BYTES  {s.max_payload}u")
    w(f"#define PROTO_MAX_RAW_BYTES      {s.max_raw_bytes}u")
    w(f"#define PROTO_MAX_WIRE_BYTES     {s.max_wire_bytes}u")
    w("")
    for cname, cval in CHANNELS.items():
        w(f"#define PROTO_CH_{cname.upper():<8} {cval}u")
    for dname, dval in DIRECTIONS.items():
        w(f"#define PROTO_DIR_{dname.upper():<12} {dval}u")
    w("")
    w("/* ---- Little-endian yardımcıları ------------------------------------ */")
    w("")
    w("static inline void proto_put_u8(uint8_t *p, uint8_t v) { p[0] = v; }")
    w("static inline void proto_put_u16(uint8_t *p, uint16_t v)")
    w("{")
    w("    p[0] = (uint8_t)(v & 0xFFu);")
    w("    p[1] = (uint8_t)((v >> 8) & 0xFFu);")
    w("}")
    w("static inline void proto_put_u32(uint8_t *p, uint32_t v)")
    w("{")
    w("    p[0] = (uint8_t)(v & 0xFFu);")
    w("    p[1] = (uint8_t)((v >> 8) & 0xFFu);")
    w("    p[2] = (uint8_t)((v >> 16) & 0xFFu);")
    w("    p[3] = (uint8_t)((v >> 24) & 0xFFu);")
    w("}")
    w("static inline void proto_put_i16(uint8_t *p, int16_t v) { proto_put_u16(p, (uint16_t)v); }")
    w("static inline void proto_put_i32(uint8_t *p, int32_t v) { proto_put_u32(p, (uint32_t)v); }")
    w("")
    w("static inline uint8_t proto_get_u8(const uint8_t *p) { return p[0]; }")
    w("static inline uint16_t proto_get_u16(const uint8_t *p)")
    w("{")
    w("    return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));")
    w("}")
    w("static inline uint32_t proto_get_u32(const uint8_t *p)")
    w("{")
    w("    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);")
    w("}")
    w("static inline int16_t proto_get_i16(const uint8_t *p) { return (int16_t)proto_get_u16(p); }")
    w("static inline int32_t proto_get_i32(const uint8_t *p) { return (int32_t)proto_get_u32(p); }")
    w("")
    w("/* ---- Numaralandırmalar ---------------------------------------------- */")
    for ename, values in s.enums.items():
        prefix = _c_enum_prefix(ename)
        w("")
        if s.enum_docs.get(ename):
            w(f"/* {_c_doc(s.enum_docs[ename])} */")
        w("typedef enum {")
        for vname, v in values.items():
            w(f"    {prefix}_{vname} = {v},")
        w(f"}} {prefix.lower()}_t;")
        w("")
        w(f"static inline bool {prefix.lower()}_is_valid(uint8_t v)")
        w("{")
        w("    switch (v) {")
        for v in sorted(set(values.values())):
            w(f"    case {v}u:")
        w("        return true;")
        w("    default:")
        w("        return false;")
        w("    }")
        w("}")
    w("")
    w("/* ---- Mesajlar -------------------------------------------------------- */")
    for m in s.messages:
        up = m.name
        w("")
        w(f"/* {m.name}  id=0x{m.id:02X}  kanal={m.channel}  yön={m.dir}"
          f"{'  can_id=0x%03X' % m.can_id if m.can_id is not None else ''}"
          f"{'  İMZASIZ' if not m.auth else ''}")
        if m.doc:
            w(f" * {_c_doc(m.doc)}")
        w(" */")
        w(f"#define PROTO_ID_{up:<18} 0x{m.id:02X}u")
        w(f"#define PROTO_SIZE_{up:<16} {m.size}u")
        if m.can_id is not None:
            w(f"#define PROTO_CAN_ID_{up:<14} 0x{m.can_id:03X}u")
        if not m.fields:
            continue
        w("typedef struct {")
        for f in m.fields:
            ctype = PRIMITIVES[f.type][3]
            notes = []
            if f.enum:
                notes.append(f"enum {f.enum}")
            if f.unit:
                notes.append(f.unit)
            comment = f"  /* {', '.join(notes)} */" if notes else ""
            w(f"    {ctype} {f.name};{comment}")
        w(f"}} proto_{m.c_name}_t;")
        w("")
        w(f"static inline void proto_{m.c_name}_encode(const proto_{m.c_name}_t *m, uint8_t *buf)")
        w("{")
        off = 0
        for f in m.fields:
            w(f"    proto_put_{f.type}(buf + {off}, m->{f.name});")
            off += f.size
        w("}")
        w("")
        w(f"static inline bool proto_{m.c_name}_decode(const uint8_t *buf, size_t len, proto_{m.c_name}_t *m)")
        w("{")
        w(f"    if (len != PROTO_SIZE_{up}) {{")
        w("        return false;")
        w("    }")
        off = 0
        for f in m.fields:
            w(f"    m->{f.name} = proto_get_{f.type}(buf + {off});")
            off += f.size
        for f in m.fields:
            if f.enum:
                w(f"    if (!{_c_enum_prefix(f.enum).lower()}_is_valid(m->{f.name})) {{")
                w("        return false;")
                w("    }")
        w("    return true;")
        w("}")
    w("")
    w("/* ---- Mesaj tablosu ---------------------------------------------------- */")
    w("")
    w("typedef struct {")
    w("    uint8_t id;")
    w("    uint8_t size;")
    w("    uint8_t channel;  /* PROTO_CH_*  */")
    w("    uint8_t dir;      /* PROTO_DIR_* */")
    w("    bool auth;")
    w("    bool has_can_id;")
    w("    uint16_t can_id;")
    w("    const char *name;")
    w("} proto_msg_info_t;")
    w("")
    w("/* Bilinmeyen kimlikte NULL döner (STATUS.err_type). */")
    w("static inline const proto_msg_info_t *proto_msg_info(uint8_t id)")
    w("{")
    w("    static const proto_msg_info_t table[] = {")
    for m in s.messages:
        can = f"true, 0x{m.can_id:03X}u" if m.can_id is not None else "false, 0u"
        w(f"        {{PROTO_ID_{m.name}, PROTO_SIZE_{m.name}, PROTO_CH_{m.channel.upper()}, "
          f"PROTO_DIR_{m.dir.upper()}, {'true' if m.auth else 'false'}, {can}, \"{m.name}\"}},")
    w("    };")
    w("    for (size_t i = 0; i < sizeof table / sizeof table[0]; ++i) {")
    w("        if (table[i].id == id) {")
    w("            return &table[i];")
    w("        }")
    w("    }")
    w("    return NULL;")
    w("}")
    w("")
    w("#endif /* PROTO_MSGS_H */")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
#  Python üretimi
# --------------------------------------------------------------------------

def render_py(s: Schema) -> str:
    L: list[str] = []
    w = L.append
    w('"""' + GENERATED_NOTE.splitlines()[0])
    w("")
    for line in GENERATED_NOTE.splitlines()[1:]:
        w(line)
    w("")
    w("Mesaj tanımları, kodlayıcılar ve çözücüler. Çerçeveleme frame.py'de.")
    w('"""')
    w("from __future__ import annotations")
    w("")
    w("import struct")
    w("from dataclasses import dataclass")
    w("from enum import IntEnum")
    w("from typing import ClassVar, Dict, Optional, Type")
    w("")
    w(f"SCHEMA_VERSION = {s.version}")
    w(f"SCHEMA_HASH = 0x{s.hash:08X}")
    w("FRAME_DELIMITER = 0x00")
    w(f'HEADER_FORMAT = "{s.header_format}"  # type, seq, ts_ms')
    w(f"HEADER_BYTES = {s.header_bytes}")
    w(f"TAG_BYTES = {s.tag_bytes}")
    w("CRC_BYTES = 2")
    w(f"MAX_PAYLOAD_BYTES = {s.max_payload}")
    w(f"MAX_RAW_BYTES = {s.max_raw_bytes}")
    w(f"MAX_WIRE_BYTES = {s.max_wire_bytes}")
    w("")
    w("")
    w("class Channel(IntEnum):")
    for cname, cval in CHANNELS.items():
        w(f"    {cname.upper()} = {cval}")
    w("")
    w("")
    w("class Direction(IntEnum):")
    for dname, dval in DIRECTIONS.items():
        w(f"    {dname.upper()} = {dval}")
    for ename, values in s.enums.items():
        w("")
        w("")
        w(f"class {ename}(IntEnum):")
        if s.enum_docs.get(ename):
            w(f'    """{_py_doc(s.enum_docs[ename])}"""')
            w("")
        for vname, v in values.items():
            w(f"    {vname} = {v}")
    for m in s.messages:
        w("")
        w("")
        w("@dataclass(frozen=True)")
        w(f"class {m.class_name}:")
        w(f'    """{m.name}: {_py_doc(m.doc)}"""' if m.doc else f'    """{m.name}"""')
        w("")
        w(f"    ID: ClassVar[int] = 0x{m.id:02X}")
        w(f'    NAME: ClassVar[str] = "{m.name}"')
        w(f"    CHANNEL: ClassVar[Channel] = Channel.{m.channel.upper()}")
        w(f"    DIRECTION: ClassVar[Direction] = Direction.{m.dir.upper()}")
        w(f"    AUTH: ClassVar[bool] = {m.auth}")
        w(f"    CAN_ID: ClassVar[Optional[int]] = {('0x%03X' % m.can_id) if m.can_id is not None else 'None'}")
        w(f'    FORMAT: ClassVar[str] = "{m.struct_format}"')
        w(f"    SIZE: ClassVar[int] = {m.size}")
        if m.fields:
            w("")
            for f in m.fields:
                w(f"    {f.name}: {f.enum or 'int'}")
        w("")
        w("    def pack(self) -> bytes:")
        if m.fields:
            args = ", ".join(f"int(self.{f.name})" for f in m.fields)
            w(f"        return struct.pack(self.FORMAT, {args})")
        else:
            w('        return b""')
        w("")
        w("    @classmethod")
        w(f'    def unpack(cls, data: bytes) -> "{m.class_name}":')
        w("        if len(data) != cls.SIZE:")
        w('            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")')
        if m.fields:
            w("        v = struct.unpack(cls.FORMAT, data)")
            args = ", ".join((f"{f.enum}(v[{i}])" if f.enum else f"v[{i}]")
                             for i, f in enumerate(m.fields))
            w(f"        return cls({args})")
        else:
            w("        return cls()")
    w("")
    w("")
    w("MESSAGES_BY_ID: Dict[int, Type] = {")
    for m in s.messages:
        w(f"    0x{m.id:02X}: {m.class_name},")
    w("}")
    w("")
    w("MESSAGES_BY_NAME: Dict[str, Type] = {cls.NAME: cls for cls in MESSAGES_BY_ID.values()}")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
#  Test vektörleri (C uygulaması Faz 2'de bunları birebir üretmeli)
# --------------------------------------------------------------------------

COBS_CASES = [
    "",
    "00",
    "0000",
    "11220033",
    "11223344",
    "11000000",
    "".join(f"{b:02x}" for b in range(1, 255)),          # 254 sıfırsız bayt
    "00" + "".join(f"{b:02x}" for b in range(1, 255)),   # 00 + 254
    "".join(f"{b:02x}" for b in range(1, 256)),          # 255 sıfırsız bayt
]


def _sample_value(s: Schema, f: Field, k: int) -> int:
    if f.enum:
        return max(s.enums[f.enum].values())
    return {
        "u8": (0x11 * (k + 1)) & 0xFF,
        "u16": 0x1234 + k,
        "u32": 0x89ABCDEF - k,
        "i16": -(1000 + k) if k % 2 == 0 else 1000 + k,
        "i32": -(100000 + k) if k % 2 == 0 else 100000 + k,
    }[f.type]


def _load_reference(py_code: str):
    """Üretilen messages.py'yi bellekten yükleyip referans çerçeveleyiciyi içe aktar."""
    for name in list(sys.modules):
        if name == "ika_protocol" or name.startswith("ika_protocol."):
            del sys.modules[name]
    if str(PY_PKG_DIR) not in sys.path:
        sys.path.insert(0, str(PY_PKG_DIR))
    pkg = importlib.import_module("ika_protocol")
    mod = types.ModuleType("ika_protocol.messages")
    mod.__file__ = str(OUT_PY)
    sys.modules["ika_protocol.messages"] = mod   # dataclass exec sırasında burada arar
    exec(compile(py_code, str(OUT_PY), "exec"), mod.__dict__)
    pkg.messages = mod
    frame = importlib.import_module("ika_protocol.frame")
    return mod, frame


def build_vectors(s: Schema, py_code: str) -> str:
    msgs, fr = _load_reference(py_code)

    out = {
        "doc": ("Faz 2'deki C çerçeveleyicisi bu baytları birebir üretmeli ve "
                "bad_frames'i belirtilen türle reddetmeli. Anahtar YALNIZCA TEST içindir."),
        "schema_hash": f"0x{s.hash:08X}",
        "test_key_hex": TEST_KEY.hex(),
        "session_id": TEST_SESSION_ID,
        "crc16_ccitt_false": [
            {"input_hex": b"123456789".hex(), "crc": "0x%04X" % fr.crc16_ccitt_false(b"123456789")},
        ],
        "cobs": [
            {"decoded_hex": d, "encoded_hex": fr.cobs_encode(bytes.fromhex(d)).hex()}
            for d in COBS_CASES
        ],
        "messages": [],
        "frames": [],
        "bad_frames": [],
    }

    for idx, m in enumerate(s.messages):
        cls = msgs.MESSAGES_BY_NAME[m.name]
        values = {f.name: _sample_value(s, f, k) for k, f in enumerate(m.fields)}
        inst = cls(**{f.name: (getattr(msgs, f.enum)(values[f.name]) if f.enum else values[f.name])
                      for f in m.fields})
        payload = inst.pack()
        assert cls.unpack(payload) == inst
        out["messages"].append({"name": m.name, "id": m.id, "fields": values,
                                "payload_hex": payload.hex()})

        seq, ts = 1000 + idx, 50000 + 10 * idx
        frame = fr.Frame(m.id, seq, ts, payload)
        wire = fr.encode_frame(frame, TEST_KEY, TEST_SESSION_ID)
        channel = msgs.Channel.AGENT if m.channel in ("agent", "both") else msgs.Channel.VEHICLE
        decoded, _ = fr.decode_frame(wire[:-1], key=TEST_KEY, session_id=TEST_SESSION_ID,
                                     channel=channel, direction=cls.DIRECTION)
        assert decoded == frame
        out["frames"].append({"name": m.name, "seq": seq, "ts_ms": ts, "payload_hex": payload.hex(),
                              "raw_hex": fr.cobs_decode(wire[:-1]).hex(), "wire_hex": wire.hex()})

    # Belgedeki örnek (docs/protocol.md §4.4)
    example = fr.Frame(msgs.VelocityCmd.ID, 1, 1000, msgs.VelocityCmd(250, -500).pack())
    ex_wire = fr.encode_frame(example, TEST_KEY, TEST_SESSION_ID)
    ex_raw = fr.cobs_decode(ex_wire[:-1])
    out["example"] = {"name": "VELOCITY_CMD", "fields": {"v_mm_s": 250, "w_mrad_s": -500},
                      "seq": 1, "ts_ms": 1000, "raw_hex": ex_raw.hex(), "wire_hex": ex_wire.hex()}

    def bad(desc, raw_bytes, expect, channel="agent", direction="pc_to_board", session=TEST_SESSION_ID):
        out["bad_frames"].append({"desc": desc, "wire_hex": (fr.cobs_encode(raw_bytes) + b"\x00").hex(),
                                  "receive_channel": channel, "receive_dir": direction,
                                  "session_id": session, "expect": expect})

    def with_crc(body_and_tag: bytes) -> bytes:
        return body_and_tag + fr.crc16_ccitt_false(body_and_tag).to_bytes(2, "little")

    flipped = bytearray(ex_raw)
    flipped[s.header_bytes] ^= 0x01
    bad("Yükte bir bit değişti, CRC düzeltilmedi", bytes(flipped), "crc")
    bad("Yükte bir bit değişti, CRC yeniden hesaplandı (etiket tutmaz)",
        with_crc(bytes(flipped[:-2])), "auth")
    bad("Başka bir oturumun geçerli çerçevesi", ex_raw, "auth", session=TEST_SESSION_ID ^ 1)
    tele = fr.cobs_decode(bytes.fromhex(
        next(f for f in out["frames"] if f["name"] == "TELEMETRY")["wire_hex"])[:-1])
    bad("TELEMETRY ajan kanalından geldi (araç kanalına ait)", tele, "type")
    short_body = ex_raw[:s.header_bytes] + ex_raw[s.header_bytes:s.header_bytes + 3]
    bad("VELOCITY_CMD yükü 3 bayt (4 olmalı)",
        with_crc(short_body + fr.compute_tag(TEST_KEY, TEST_SESSION_ID, short_body)), "type")
    unknown = bytes([0x7E]) + ex_raw[1:s.header_bytes]
    bad("Bilinmeyen tip 0x7E", with_crc(unknown + fr.compute_tag(TEST_KEY, TEST_SESSION_ID, unknown)), "type")
    out["bad_frames"].append({"desc": "COBS kodu çerçeve sonunun ötesini gösteriyor",
                              "wire_hex": "0511223300", "receive_channel": "agent",
                              "receive_dir": "pc_to_board", "session_id": TEST_SESSION_ID,
                              "expect": "framing"})

    # Her kötü çerçevenin gerçekten beklenen türle reddedildiğini doğrula
    for b in out["bad_frames"]:
        try:
            fr.decode_frame(bytes.fromhex(b["wire_hex"])[:-1], key=TEST_KEY, session_id=b["session_id"],
                            channel=msgs.Channel[b["receive_channel"].upper()],
                            direction=msgs.Direction[b["receive_dir"].upper()])
        except fr.FrameError as e:
            assert e.kind == b["expect"], (b["desc"], e.kind)
        else:
            raise AssertionError(f"reddedilmedi: {b['desc']}")

    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="dosya yazma; güncel değilse 1 ile çık")
    args = ap.parse_args()

    try:
        schema = load_schema()
    except SchemaError as e:
        print(f"messages.yaml hatası: {e}", file=sys.stderr)
        return 2

    py_code = render_py(schema)
    outputs = {OUT_C: render_c(schema), OUT_PY: py_code, OUT_VECTORS: build_vectors(schema, py_code)}

    if args.check:
        stale = [p for p, text in outputs.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"GÜNCEL DEĞİL: {p.relative_to(ROOT)}", file=sys.stderr)
        if stale:
            print("Çalıştır: python3 tools/gen_protocol.py", file=sys.stderr)
            return 1
        print(f"Güncel. Şema özeti 0x{schema.hash:08X}")
        return 0

    for p, text in outputs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"yazıldı: {p.relative_to(ROOT)}")
    print(f"{len(schema.messages)} mesaj · şema özeti 0x{schema.hash:08X} · "
          f"en uzun çerçeve {schema.max_encoded_bytes} bayt (sınır {schema.max_wire_bytes})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
