"""OTOMATİK ÜRETİLDİ. ELLE DÜZENLEMEYİN.

Kaynak: shared/protocol/messages.yaml
Üretici: tools/gen_protocol.py

Mesaj tanımları, kodlayıcılar ve çözücüler. Çerçeveleme frame.py'de.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, Dict, Optional, Type

SCHEMA_VERSION = 1
SCHEMA_HASH = 0xD9092C66
FRAME_DELIMITER = 0x00
HEADER_FORMAT = "<BII"  # type, seq, ts_ms
HEADER_BYTES = 9
TAG_BYTES = 8
CRC_BYTES = 2
MAX_PAYLOAD_BYTES = 23
MAX_RAW_BYTES = 42
MAX_WIRE_BYTES = 64


class Channel(IntEnum):
    AGENT = 1
    VEHICLE = 2
    BOTH = 3


class Direction(IntEnum):
    PC_TO_BOARD = 0
    BOARD_TO_PC = 1


class BoardState(IntEnum):
    """Kartın durum makinesi (docs/RULES.md §5.2)"""

    NORMAL = 0
    RECOVERY = 1
    HOLD = 2


class Result(IntEnum):
    ACCEPTED = 0
    REJECTED = 1


class Rule(IntEnum):
    """Karara yol açan kural (docs/RULES.md §2)"""

    NONE = 0
    FRESHNESS = 3
    MODE = 4
    GEOFENCE = 5
    LIMIT = 6
    CONSISTENCY = 7


class Reason(IntEnum):
    """Kuralın alt nedeni. value/lo/hi/hint alanlarının anlamını belirler."""

    NONE = 0
    TOO_OLD = 10
    FROM_FUTURE = 11
    IN_RECOVERY = 20
    IN_HOLD = 21
    NOT_IN_HOLD = 22
    NO_HEARTBEAT = 23
    GOAL_OUTSIDE_ALLOWED = 30
    GOAL_IN_FORBIDDEN = 31
    ABOVE_MAX = 40
    NOT_POSITIVE = 41
    TOO_FAR = 50
    BELIEF_TOO_OLD = 51
    BELIEF_FROM_FUTURE = 52
    NO_TELEMETRY = 53


class GoalSource(IntEnum):
    """Nav2'ye giden hedefin kaynağı (kayıt ve analiz için)"""

    AGENT = 0
    RECOVERY_HOME = 1
    RECOVERY_SAFE = 2


@dataclass(frozen=True)
class HelloReq:
    """HELLO_REQ: Köprü, oturum bilgisini ister. Kart HELLO ile cevap verir (en fazla saniyede 2 kez). İmzasızdır çünkü köprü oturum kimliğini henüz bilmiyor olabilir. Kartın durumunu değiştirmez."""

    ID: ClassVar[int] = 0x01
    NAME: ClassVar[str] = "HELLO_REQ"
    CHANNEL: ClassVar[Channel] = Channel.BOTH
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = False
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<"
    SIZE: ClassVar[int] = 0

    def pack(self) -> bytes:
        return b""

    @classmethod
    def unpack(cls, data: bytes) -> "HelloReq":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        return cls()


@dataclass(frozen=True)
class Hello:
    """HELLO: Kart açılışta (oturum kurulana kadar 500 ms'de bir) ve HELLO_REQ'e cevaben gönderir. Başlıktaki ts_ms kartın o anki saatidir."""

    ID: ClassVar[int] = 0x81
    NAME: ClassVar[str] = "HELLO"
    CHANNEL: ClassVar[Channel] = Channel.BOTH
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<IIIB"
    SIZE: ClassVar[int] = 13

    session_id: int
    last_rx_seq: int
    schema_hash: int
    state: BoardState

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.session_id), int(self.last_rx_seq), int(self.schema_hash), int(self.state))

    @classmethod
    def unpack(cls, data: bytes) -> "Hello":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1], v[2], BoardState(v[3]))


@dataclass(frozen=True)
class Heartbeat:
    """HEARTBEAT: Köprü 100 ms'de bir gönderir. Aynı zamanda saat eşitleme örneğidir. Zaman aşımı 500 ms (docs/RULES.md §3.5)."""

    ID: ClassVar[int] = 0x02
    NAME: ClassVar[str] = "HEARTBEAT"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<I"
    SIZE: ClassVar[int] = 4

    echo_pc_ms: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.echo_pc_ms))

    @classmethod
    def unpack(cls, data: bytes) -> "Heartbeat":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0])


@dataclass(frozen=True)
class HeartbeatAck:
    """HEARTBEAT_ACK: Her HEARTBEAT'e cevap. Başlıktaki ts_ms, saat eşitlemesi için kartın saatidir."""

    ID: ClassVar[int] = 0x82
    NAME: ClassVar[str] = "HEARTBEAT_ACK"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<IBB"
    SIZE: ClassVar[int] = 6

    echo_pc_ms: int
    state: BoardState
    reject_streak: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.echo_pc_ms), int(self.state), int(self.reject_streak))

    @classmethod
    def unpack(cls, data: bytes) -> "HeartbeatAck":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], BoardState(v[1]), v[2])


@dataclass(frozen=True)
class Status:
    """STATUS: Saniyede bir, o kanala ait sayaçlar. Açılıştan beri birikimlidir, uint16 olarak taşar. \"Bozuk çerçeve sessizce atılmaz, sayılır ve raporlanır.\""""

    ID: ClassVar[int] = 0x83
    NAME: ClassVar[str] = "STATUS"
    CHANNEL: ClassVar[Channel] = Channel.BOTH
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<BBHHHHHHHHH"
    SIZE: ClassVar[int] = 20

    state: BoardState
    reject_streak: int
    frames_ok: int
    err_framing: int
    err_crc: int
    err_type: int
    err_auth: int
    err_replay: int
    err_fresh: int
    clipped: int
    telemetry_age_ms: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.state), int(self.reject_streak), int(self.frames_ok), int(self.err_framing), int(self.err_crc), int(self.err_type), int(self.err_auth), int(self.err_replay), int(self.err_fresh), int(self.clipped), int(self.telemetry_age_ms))

    @classmethod
    def unpack(cls, data: bytes) -> "Status":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(BoardState(v[0]), v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10])


@dataclass(frozen=True)
class VelocityCmd:
    """VELOCITY_CMD: Nav2'nin hız komutu, 20 Hz. İhlalde kırpılır, VERDICT gönderilmez."""

    ID: ClassVar[int] = 0x10
    NAME: ClassVar[str] = "VELOCITY_CMD"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<hh"
    SIZE: ClassVar[int] = 4

    v_mm_s: int
    w_mrad_s: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.v_mm_s), int(self.w_mrad_s))

    @classmethod
    def unpack(cls, data: bytes) -> "VelocityCmd":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1])


@dataclass(frozen=True)
class GotoCmd:
    """GOTO_CMD: Ajan: git(yer). Denetim: GEOFENCE, CONSISTENCY."""

    ID: ClassVar[int] = 0x20
    NAME: ClassVar[str] = "GOTO_CMD"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<hhhhhI"
    SIZE: ClassVar[int] = 14

    goal_x_cm: int
    goal_y_cm: int
    goal_yaw_mrad: int
    belief_x_cm: int
    belief_y_cm: int
    belief_ts_ms: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.goal_x_cm), int(self.goal_y_cm), int(self.goal_yaw_mrad), int(self.belief_x_cm), int(self.belief_y_cm), int(self.belief_ts_ms))

    @classmethod
    def unpack(cls, data: bytes) -> "GotoCmd":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1], v[2], v[3], v[4], v[5])


@dataclass(frozen=True)
class WaitCmd:
    """WAIT_CMD: Ajan: bekle(süre). Denetim: CONSISTENCY. Araç tarafına HALT(süre) olarak gider."""

    ID: ClassVar[int] = 0x21
    NAME: ClassVar[str] = "WAIT_CMD"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<HhhI"
    SIZE: ClassVar[int] = 10

    duration_s: int
    belief_x_cm: int
    belief_y_cm: int
    belief_ts_ms: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.duration_s), int(self.belief_x_cm), int(self.belief_y_cm), int(self.belief_ts_ms))

    @classmethod
    def unpack(cls, data: bytes) -> "WaitCmd":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1], v[2], v[3])


@dataclass(frozen=True)
class SpeedLimitCmd:
    """SPEED_LIMIT_CMD: Ajan: hiz_siniri(değer). Denetim: LIMIT (0 < değer ≤ 300), CONSISTENCY."""

    ID: ClassVar[int] = 0x22
    NAME: ClassVar[str] = "SPEED_LIMIT_CMD"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<HhhI"
    SIZE: ClassVar[int] = 10

    limit_mm_s: int
    belief_x_cm: int
    belief_y_cm: int
    belief_ts_ms: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.limit_mm_s), int(self.belief_x_cm), int(self.belief_y_cm), int(self.belief_ts_ms))

    @classmethod
    def unpack(cls, data: bytes) -> "SpeedLimitCmd":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1], v[2], v[3])


@dataclass(frozen=True)
class StopCmd:
    """STOP_CMD: Ajan: dur(). Durmak her zaman güvenlidir: MODE ve içerik kuralları uygulanmaz, konum inancı taşımaz. Yalnızca AUTH, REPLAY, FRESHNESS."""

    ID: ClassVar[int] = 0x23
    NAME: ClassVar[str] = "STOP_CMD"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<"
    SIZE: ClassVar[int] = 0

    def pack(self) -> bytes:
        return b""

    @classmethod
    def unpack(cls, data: bytes) -> "StopCmd":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        return cls()


@dataclass(frozen=True)
class ResetCmd:
    """RESET_CMD: SIFIRLA. Yalnızca HOLD'da ve kalp atışı canlıyken kabul edilir. HOLD → NORMAL."""

    ID: ClassVar[int] = 0x30
    NAME: ClassVar[str] = "RESET_CMD"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<"
    SIZE: ClassVar[int] = 0

    def pack(self) -> bytes:
        return b""

    @classmethod
    def unpack(cls, data: bytes) -> "ResetCmd":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        return cls()


@dataclass(frozen=True)
class Verdict:
    """VERDICT: İmzası doğrulanmış her görev komutu ve RESET_CMD için karar. Kart her yapılandırmada TAM gerekçeyi gönderir. C yapılandırmasında gerekçeyi ajandan köprü gizler (docs/protocol.md §7)."""

    ID: ClassVar[int] = 0x90
    NAME: ClassVar[str] = "VERDICT"
    CHANNEL: ClassVar[Channel] = Channel.AGENT
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = None
    FORMAT: ClassVar[str] = "<IBBBiiihh"
    SIZE: ClassVar[int] = 23

    ref_seq: int
    result: Result
    rule: Rule
    reason: Reason
    value: int
    lo: int
    hi: int
    hint_x_cm: int
    hint_y_cm: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.ref_seq), int(self.result), int(self.rule), int(self.reason), int(self.value), int(self.lo), int(self.hi), int(self.hint_x_cm), int(self.hint_y_cm))

    @classmethod
    def unpack(cls, data: bytes) -> "Verdict":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], Result(v[1]), Rule(v[2]), Reason(v[3]), v[4], v[5], v[6], v[7], v[8])


@dataclass(frozen=True)
class Telemetry:
    """TELEMETRY: Aracın harita çerçevesindeki konumu, 20 Hz. Yalnızca araç kanalından kabul edilir: ajan tarafı telemetri uyduramaz (docs/protocol.md §2)."""

    ID: ClassVar[int] = 0x40
    NAME: ClassVar[str] = "TELEMETRY"
    CHANNEL: ClassVar[Channel] = Channel.VEHICLE
    DIRECTION: ClassVar[Direction] = Direction.PC_TO_BOARD
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = 0x200
    FORMAT: ClassVar[str] = "<hhh"
    SIZE: ClassVar[int] = 6

    x_cm: int
    y_cm: int
    yaw_mrad: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.x_cm), int(self.y_cm), int(self.yaw_mrad))

    @classmethod
    def unpack(cls, data: bytes) -> "Telemetry":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1], v[2])


@dataclass(frozen=True)
class Halt:
    """HALT: Nav2 hedefini iptal et ve dur. duration_s = 0 → süresiz (STOP_CMD)."""

    ID: ClassVar[int] = 0xA3
    NAME: ClassVar[str] = "HALT"
    CHANNEL: ClassVar[Channel] = Channel.VEHICLE
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = 0x100
    FORMAT: ClassVar[str] = "<H"
    SIZE: ClassVar[int] = 2

    duration_s: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.duration_s))

    @classmethod
    def unpack(cls, data: bytes) -> "Halt":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0])


@dataclass(frozen=True)
class Drive:
    """DRIVE: Onaylı (gerekirse kırpılmış) hız komutu. HOLD'da 20 Hz sıfır hız."""

    ID: ClassVar[int] = 0xA0
    NAME: ClassVar[str] = "DRIVE"
    CHANNEL: ClassVar[Channel] = Channel.VEHICLE
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = 0x110
    FORMAT: ClassVar[str] = "<hh"
    SIZE: ClassVar[int] = 4

    v_mm_s: int
    w_mrad_s: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.v_mm_s), int(self.w_mrad_s))

    @classmethod
    def unpack(cls, data: bytes) -> "Drive":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1])


@dataclass(frozen=True)
class Goal:
    """GOAL: Onaylı hedef. Köprü Nav2'ye iletir."""

    ID: ClassVar[int] = 0xA1
    NAME: ClassVar[str] = "GOAL"
    CHANNEL: ClassVar[Channel] = Channel.VEHICLE
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = 0x120
    FORMAT: ClassVar[str] = "<hhhB"
    SIZE: ClassVar[int] = 7

    x_cm: int
    y_cm: int
    yaw_mrad: int
    source: GoalSource

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.x_cm), int(self.y_cm), int(self.yaw_mrad), int(self.source))

    @classmethod
    def unpack(cls, data: bytes) -> "Goal":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0], v[1], v[2], GoalSource(v[3]))


@dataclass(frozen=True)
class SpeedLimitSet:
    """SPEED_LIMIT_SET: Onaylı hız sınırı. Köprü Nav2'nin hız sınırı konusuna iletir."""

    ID: ClassVar[int] = 0xA2
    NAME: ClassVar[str] = "SPEED_LIMIT_SET"
    CHANNEL: ClassVar[Channel] = Channel.VEHICLE
    DIRECTION: ClassVar[Direction] = Direction.BOARD_TO_PC
    AUTH: ClassVar[bool] = True
    CAN_ID: ClassVar[Optional[int]] = 0x130
    FORMAT: ClassVar[str] = "<H"
    SIZE: ClassVar[int] = 2

    limit_mm_s: int

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, int(self.limit_mm_s))

    @classmethod
    def unpack(cls, data: bytes) -> "SpeedLimitSet":
        if len(data) != cls.SIZE:
            raise ValueError(f"{cls.NAME}: {len(data)} bayt, {cls.SIZE} bekleniyordu")
        v = struct.unpack(cls.FORMAT, data)
        return cls(v[0])


MESSAGES_BY_ID: Dict[int, Type] = {
    0x01: HelloReq,
    0x81: Hello,
    0x02: Heartbeat,
    0x82: HeartbeatAck,
    0x83: Status,
    0x10: VelocityCmd,
    0x20: GotoCmd,
    0x21: WaitCmd,
    0x22: SpeedLimitCmd,
    0x23: StopCmd,
    0x30: ResetCmd,
    0x90: Verdict,
    0x40: Telemetry,
    0xA3: Halt,
    0xA0: Drive,
    0xA1: Goal,
    0xA2: SpeedLimitSet,
}

MESSAGES_BY_NAME: Dict[str, Type] = {cls.NAME: cls for cls in MESSAGES_BY_ID.values()}
