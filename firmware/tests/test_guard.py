"""Kartın karar katmanı (firmware/app/guard/): denetim sırası ve durum makinesi.

    python3 -m pytest firmware/tests -v

guard_driver.c, kartın C kaynaklarıyla birlikte gcc (ASan, UBSan) ile derlenir.
Beklenen değerler docs/RULES.md §2, §4, §5.2, §5.4 ve docs/protocol.md §7'den.
Kural ve gerekçe numaraları üretilmiş Python modülünden gelir (K-003).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "firmware" / "app"
TESTS = ROOT / "firmware" / "tests"
PROTO = ROOT / "shared" / "protocol"
sys.path.insert(0, str(PROTO / "python"))

from ika_protocol import messages as m   # noqa: E402
from ika_protocol.messages import BoardState, GoalSource, Reason, Result, Rule   # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc yok")

HOLD, NORMAL, RECOVERY = int(BoardState.HOLD), int(BoardState.NORMAL), int(BoardState.RECOVERY)
HOME = (-100, -100)                     # guard_driver.c'deki test haritası


@dataclass
class Decision:
    ref_seq: int
    result: int
    rule: int
    reason: int
    hint: Tuple[int, int]
    goal: Optional[Tuple[int, int, int, int]]
    state: int
    streak: int
    halt: Optional[int]
    speed: Optional[int]
    value: int
    lo: int
    hi: int


def _parse(line: str) -> Decision:
    f = line.split()
    goal = None if f[6] == "-" else tuple(int(v) for v in f[6].split(","))
    return Decision(int(f[0]), int(f[1]), int(f[2]), int(f[3]), (int(f[4]), int(f[5])),
                    goal, int(f[7]), int(f[8]), None if f[9] == "-" else int(f[9]),
                    None if f[10] == "-" else int(f[10]), int(f[11]), int(f[12]), int(f[13]))


class Guard:
    def __init__(self, exe: Path) -> None:
        self.exe = exe
        self.cmds: List[str] = []

    def run(self, cmds: List[str]) -> List[str]:
        r = subprocess.run([str(self.exe)], input="\n".join(cmds) + "\n",
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        out = r.stdout.splitlines()
        assert len(out) == len(cmds)
        return out

    def seq(self, *cmds: str) -> List[Decision]:
        """Komutları tek bir sürücü çalıştırmasında, sırayla verir."""
        return [_parse(o) for c, o in zip(cmds, self.run(list(cmds)))
                if c.startswith(("goto", "reset", "wait", "stop", "speed"))]


@pytest.fixture(scope="module")
def guard(tmp_path_factory):
    exe = tmp_path_factory.mktemp("c") / "guard_driver"
    cc = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wsign-conversion",
         "-Werror", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
         "-I", str(APP), "-I", str(PROTO / "c"), str(TESTS / "guard_driver.c"),
         str(APP / "guard" / "guard.c"), str(APP / "site" / "site.c"),
         str(APP / "rules" / "geofence" / "geofence.c"), str(APP / "recovery" / "recovery.c"),
         str(APP / "rules" / "limits" / "limits.c"), str(APP / "rules" / "freshness" / "freshness.c"),
         "-o", str(exe)],
        capture_output=True, text=True)
    assert cc.returncode == 0, "Kartın C kodu katı uyarılarla derlenmedi:\n" + cc.stderr
    return Guard(exe)


def rejected(d: Decision, rule: Rule, reason: Reason) -> bool:
    return (d.result, d.rule, d.reason) == (Result.REJECTED, rule, reason) and d.goal is None


def accepted(d: Decision) -> bool:
    return (d.result, d.rule, d.reason) == (Result.ACCEPTED, Rule.NONE, Reason.NONE)


# ---- Durum makinesi (RULES §5.2) ----------------------------------------------

def test_boots_in_hold_and_rejects_goto(guard):
    (d,) = guard.seq("goto 7 100 100 0")
    assert rejected(d, Rule.MODE, Reason.IN_HOLD)
    assert d.ref_seq == 7 and d.state == HOLD


def test_reset_needs_heartbeat(guard):
    (d,) = guard.seq("reset 3 0")
    assert rejected(d, Rule.MODE, Reason.NO_HEARTBEAT)
    assert d.state == HOLD


def test_reset_enters_normal_only_from_hold(guard):
    a, b = guard.seq("reset 3 1", "reset 4 1")
    assert accepted(a) and a.state == NORMAL and a.goal is None
    assert rejected(b, Rule.MODE, Reason.NOT_IN_HOLD) and b.state == NORMAL


def test_heartbeat_loss_is_latched(guard):
    """Kalp atışı kesilince HOLD. Geri gelmesi yetmez, SIFIRLA gerekir."""
    a, b, c = guard.seq("reset 1 1", "lost", "goto 2 100 100 0", "reset 3 1")
    assert a.state == NORMAL
    assert rejected(b, Rule.MODE, Reason.IN_HOLD) and b.state == HOLD
    assert accepted(c) and c.state == NORMAL


# ---- GOTO_CMD: GEOFENCE (RULES §2, §3.1; protocol.md §7.1) -----------------------

def test_goal_inside_is_forwarded_unchanged(guard):
    _, d = guard.seq("reset 1 1", "goto 9 -1500 1200 -3141")
    assert accepted(d)
    assert d.goal == (-1500, 1200, -3141, int(GoalSource.AGENT))
    assert d.hint == (0, 0)


# Kare uzaklıklar elle hesaplandı. Güvenli noktalar: (0, 1000), (0, -1000), (1500, 1500).
@pytest.mark.parametrize("x,y,reason,hint", [
    (-2500, 0, Reason.GOAL_OUTSIDE_ALLOWED, (0, 1000)),     # ilk ikisine 7,25 M: eşitlikte ilki
    (2500, 0, Reason.GOAL_OUTSIDE_ALLOWED, (1500, 1500)),   # 3,25 M < 7,25 M
    (2000, 100, Reason.GOAL_OUTSIDE_ALLOWED, (1500, 1500)), # izinli çokgenin kenarı
    (700, 700, Reason.GOAL_IN_FORBIDDEN, (0, 1000)),        # 0,58 M < 1,28 M
    (500, 700, Reason.GOAL_IN_FORBIDDEN, (0, 1000)),        # yasak çokgenin kenarı
    (0, -2500, Reason.GOAL_OUTSIDE_ALLOWED, (0, -1000)),
], ids=["eşitlik", "dışarıda", "izinli kenar", "yasak içi", "yasak kenar", "aşağıda"])
def test_goal_rejected_with_nearest_safe_point(guard, x, y, reason, hint):
    _, d = guard.seq("reset 1 1", f"goto 9 {x} {y} 0")
    assert rejected(d, Rule.GEOFENCE, reason)
    assert d.hint == hint
    assert d.state == NORMAL


def test_reject_streak_counts_content_rejections_only(guard):
    """İçerik reddi sayılır, MODE reddi sayılmaz, kabul sıfırlar (RULES §5.4)."""
    ds = guard.seq("init", "goto 1 0 0 0",                     # MODE: sayılmaz
                   "reset 2 1",
                   "goto 3 9000 0 0", "goto 4 700 700 0", "goto 5 2000 0 0",
                   "goto 6 0 0 0",                             # kabul: sıfırlar
                   "goto 7 9000 0 0",
                   "lost", "goto 8 9000 0 0",                  # HOLD'da MODE: sayılmaz
                   "reset 9 1")                                # SIFIRLA: sıfırlar
    assert [d.streak for d in ds] == [0, 0, 1, 2, 3, 0, 1, 1, 0]


def test_reject_streak_saturates(guard):
    # kanal ölüyken kurtarma başlamaz, sayaç saymaya devam eder ve 255'te doyar
    cmds = ["init", "reset 1 1"] + [f"goto {i} 9000 0 0 0" for i in range(2, 302)]
    ds = guard.seq(*cmds)
    assert ds[-1].streak == 255 and ds[-1].state == NORMAL


# ---- En yakın güvenli nokta (RULES §5.3) -------------------------------------------

@pytest.mark.parametrize("which,p,expected", [
    (1, (0, 0), (0, 1000)),          # eşit uzaklık: sıra numarası küçük olan
    (1, (0, -1), (0, -1000)),
    (1, (1400, 1400), (1500, 1500)),
    (1, (-32768, -32768), (0, -1000)),   # 64 bit kare uzaklık
    (0, (500, 500), (-100, -100)),   # güvenli nokta yok: başlangıç
])
def test_nearest_safe(guard, which, p, expected):
    (out,) = guard.run([f"nearest {which} {p[0]} {p[1]}"])
    assert tuple(int(v) for v in out.split()) == expected


# ---- Hız komutu (K-031, asgari aktarma) ----------------------------------------

def test_velocity_forwarded_only_outside_hold(guard):
    out = guard.run(["vel 300 -500",            # HOLD'da açılır: aktarılmaz
                     "reset 1 1",
                     "vel 300 -500",            # 0'dan: hızlanma adımı 30 / 60 (K-046)
                     "vel -32768 32767",        # işaret değişimi serbest, sonra ±600
                     "vel 0 0",
                     "lost",
                     "vel 300 -500"])           # kalp atışı kesildi: HOLD, aktarılmaz
    assert out[0] == "-"
    assert out[2:5] == ["30,-60 c", "-600,600 c", "0,0"]
    assert out[6] == "-"


def test_velocity_does_not_change_state_or_streak(guard):
    d = guard.seq("reset 1 1", "goto 2 5000 0 0", "vel 100 100", "goto 3 5000 0 0")
    assert (d[1].streak, d[2].streak) == (1, 2)   # aradaki hız komutu sayacı sıfırlamadı
    assert d[2].state == NORMAL


# ---- Kurtarma (RULES §5.2–§5.4, K-047) -------------------------------------------

def _tel(out: str):
    goal, state = out.split()
    return (None if goal == "-" else tuple(int(v) for v in goal.split(","))), int(state)


def test_fifth_content_rejection_starts_recovery_home(guard):
    ds = guard.seq("init", "reset 1 1", *[f"goto {i} 9000 0 0" for i in range(2, 7)])
    *first4, fifth = ds[1:]
    assert all(d.state == NORMAL and d.goal is None for d in first4)
    # ajan 5. reddin VERDICT'ini yine alır; aynı kararda araca başlangıç hedefi gider
    assert fifth.result == Result.REJECTED and fifth.rule == Rule.GEOFENCE
    assert fifth.state == RECOVERY and fifth.streak == 5
    assert fifth.goal == (*HOME, 0, int(GoalSource.RECOVERY_HOME))


def test_fifth_rejection_with_dead_channel_does_not_recover(guard):
    ds = guard.seq("init", "reset 1 1", *[f"goto {i} 9000 0 0 0" for i in range(2, 7)])
    assert ds[-1].state == NORMAL and ds[-1].goal is None and ds[-1].streak == 5


@pytest.mark.parametrize("x,y,goal", [
    (700, 700, (0, 1000)),          # yasak bölgede: en yakın güvenli nokta
    (2500, 2500, (1500, 1500)),     # izinli alanın dışında
])
def test_vehicle_outside_starts_recovery_safe(guard, x, y, goal):
    out = guard.run(["init", "reset 1 1", f"tel {x} {y} 1"])
    assert _tel(out[2]) == ((*goal, 0, int(GoalSource.RECOVERY_SAFE)), RECOVERY)


def test_vehicle_position_ignored_unless_normal_and_alive(guard):
    out = guard.run(["init", "tel 700 700 1",              # HOLD: kurtarma yalnız NORMAL'den
                     "reset 1 1", "tel 0 0 1",             # içeride: bir şey olmaz
                     "tel 700 700 0"])                     # kanal ölü: kalp atışı zaten HOLD'a alır
    assert [_tel(out[i]) for i in (1, 3, 4)] == [(None, HOLD), (None, NORMAL), (None, NORMAL)]


def test_recovery_rejects_agent_but_passes_velocity(guard):
    out = guard.run(["init", "reset 1 1", "tel 700 700 1",
                     "goto 2 0 0 0", "reset 3 1", "vel 200 -100"])
    goto, reset = _parse(out[3]), _parse(out[4])
    assert rejected(goto, Rule.MODE, Reason.IN_RECOVERY) and goto.streak == 0   # MODE sayılmaz
    assert rejected(reset, Rule.MODE, Reason.NOT_IN_HOLD) and reset.state == RECOVERY
    assert out[5] == "30,-60 c"                  # RECOVERY'de de kırpılarak geçer


def test_arrival_within_35_cm_enters_hold(guard):
    # hedef (0, 1000); 36 cm ve 35,6 cm uzakta sürer, tam 35 cm'de (sınır dahil) HOLD
    out = guard.run(["init", "reset 1 1", "tel 700 700 1",
                     "tel 0 1036 1", "tel 22 1028 1", "tel 21 1028 1", "vel 100 0"])
    assert [_tel(o)[1] for o in out[3:6]] == [RECOVERY, RECOVERY, HOLD]   # 21²+28² = 35²
    assert out[6] == "-"                                                   # HOLD: hız geçmez


def test_telemetry_timeout_in_recovery_enters_hold(guard):
    out = guard.run(["init", "tick 0 100000",                          # HOLD: etkisiz
                     "reset 1 1", "tick 0 100000",                     # NORMAL: etkisiz
                     "tel 700 700 1", "tick 0 500", "tick 0 501"])     # RECOVERY: > 500 ms HOLD
    assert [int(out[i]) for i in (1, 3, 5, 6)] == [HOLD, NORMAL, RECOVERY, HOLD]


def test_recovery_timeout_enters_hold(guard):
    # süre girişten sonraki ilk tick'te başlar: 1000'de giriş, 181000'de sürer, 181001'de HOLD
    out = guard.run(["init", "reset 1 1", "tick 999999 0",             # NORMAL: etkisiz
                     "tel 700 700 1", "tick 1000 0", "tick 181000 0", "tick 181001 0"])
    assert [int(out[i]) for i in (2, 4, 5, 6)] == [NORMAL, RECOVERY, RECOVERY, HOLD]


def test_recovery_timeout_restarts_on_each_entry(guard):
    # ilk kurtarma varışla bitti; ikinci kurtarmanın süresi kendi girişinden sayılır
    out = guard.run(["init", "reset 1 1", "tel 700 700 1", "tick 0 0", "tel 0 1000 1",
                     "reset 2 1", "tel 700 700 1", "tick 200000 0", "tick 380000 0",
                     "tick 380001 0"])
    assert [int(out[i]) for i in (7, 8, 9)] == [RECOVERY, RECOVERY, HOLD]


def test_recovery_timeout_survives_tick_wraparound(guard):
    # HAL_GetTick 49 günde taşar: giriş taşmadan 296 ms önce, fark işaretsiz alınır.
    # 179704'te geçen süre 296 + 179704 = 180000 (sürer), 179705'te 180001 (HOLD)
    out = guard.run(["init", "reset 1 1", "tel 700 700 1", "tick 4294967000 0",
                     "tick 179704 0", "tick 179705 0"])
    assert [int(out[i]) for i in (4, 5)] == [RECOVERY, HOLD]


def test_heartbeat_loss_in_recovery_is_latched(guard):
    out = guard.run(["init", "reset 1 1", "tel 700 700 1", "lost",
                     "tel 0 1000 1",                    # hedefte bile olsa HOLD'da kalır
                     "goto 2 0 0 0"])
    assert _tel(out[4]) == (None, HOLD)
    assert rejected(_parse(out[5]), Rule.MODE, Reason.IN_HOLD)


# ---- Bekle ve dur (WAIT_CMD, STOP_CMD), HOLD'da HALT (K-042, K-048) --------------

def test_wait_rejected_outside_normal_accepted_in_normal(guard):
    hold, _, normal = guard.seq("init", "wait 1 30", "reset 2 1", "wait 3 30")
    assert rejected(hold, Rule.MODE, Reason.IN_HOLD) and hold.halt is None
    assert accepted(normal) and normal.halt == 30 and normal.goal is None and normal.state == NORMAL


def test_wait_rejected_in_recovery(guard):
    out = guard.run(["init", "reset 1 1", "tel 700 700 1", "wait 2 30"])
    d = _parse(out[3])
    assert rejected(d, Rule.MODE, Reason.IN_RECOVERY) and d.halt is None


def test_accepted_wait_resets_streak_stop_does_not(guard):
    ds = guard.seq("init", "reset 1 1", "goto 2 9000 0 0", "goto 3 9000 0 0", "stop 4",
                   "goto 5 9000 0 0", "wait 6 10")
    assert [d.streak for d in ds[1:]] == [1, 2, 2, 3, 0]


def test_stop_cannot_dodge_recovery(guard):
    # araya "dur" koyarak 5. içerik reddi kurtarmayı yine başlatır (K-048)
    cmds = ["init", "reset 1 1"]
    for i in range(5):
        cmds += [f"goto {10 + i} 9000 0 0", f"stop {20 + i}"]
    ds = guard.seq(*cmds)
    assert ds[-2].state == RECOVERY and ds[-2].goal is not None   # 5. ret


@pytest.mark.parametrize("setup,state_after", [
    ([], HOLD),                                   # açılış: HOLD
    (["reset 1 1"], NORMAL),
    (["reset 1 1", "tel 700 700 1"], HOLD),       # RECOVERY → HOLD
])
def test_stop_always_accepted_halt_zero(guard, setup, state_after):
    out = guard.run(["init", *setup, "stop 9"])
    d = _parse(out[-1])
    assert accepted(d) and d.halt == 0 and d.goal is None and d.state == state_after


def test_hold_entry_raises_halt_once(guard):
    # HOLD'a giden her yolda araca bir kez HALT(0) (K-042); HOLD'da kalmak yeniden kurmaz
    paths = {
        "kalp atışı": ["reset 1 1", "lost"],
        "varış": ["reset 1 1", "tel 700 700 1", "tel 0 1000 1"],
        "telemetri": ["reset 1 1", "tel 700 700 1", "tick 0 501"],
        "süre": ["reset 1 1", "tel 700 700 1", "tick 0 0", "tick 180001 0"],
    }
    for name, steps in paths.items():
        out = guard.run(["init", "takehalt", *steps, "takehalt", "takehalt", "lost", "takehalt"])
        assert (out[1], out[-4], out[-3], out[-1]) == ("0", "1", "0", "0"), name


def test_stop_in_recovery_does_not_double_halt(guard):
    # STOP kararı HALT(0)'ı kendisi taşır: HOLD girişi ayrıca HALT kurmaz
    out = guard.run(["init", "reset 1 1", "tel 700 700 1", "stop 2", "takehalt"])
    assert _parse(out[3]).halt == 0 and out[4] == "0"


# ---- Fiziksel limitler (RULES §3.2, K-046) ---------------------------------------

def _vel(guard, *cmds):
    return guard.run(["init", "reset 1 1", *[f"vel {v} {w}" for v, w in cmds]])[2:]


def test_acceleration_step_boundary(guard):
    # adım tam 30 mm/s ve 60 mrad/s geçer, bir fazlası kırpılır
    assert _vel(guard, (30, 60), (61, 121), (91, 181)) == ["30,60", "60,120 c", "90,180 c"]


def test_ramp_reaches_max_and_caps(guard):
    out = _vel(guard, *[(1000, 0)] * 21)
    assert out[19] == "600,0 c" and out[20] == "600,0 c"     # 20 adımda 600, sonra ±600 sınırı


def test_deceleration_and_sign_change_are_free(guard):
    out = _vel(guard, (30, 0), (60, 0), (90, 0), (0, 0), (30, 0), (-30, 0), (-200, 0))
    # 90 → 0 (durma) ve 30 → −30 (işaret değişimi) serbest; −30 → −200 hızlanma: −60
    assert out[3:] == ["0,0", "30,0", "-30,0", "-60,0 c"]


def test_speed_cap_applies_even_when_decelerating(guard):
    # yön değişiminde büyüklük ±600'ü aşamaz (bilinen sınır yalnız ivme için)
    out = _vel(guard, (30, 60), (-32768, -32768))
    assert out[1] == "-600,-600 c"


def test_hold_resets_previous_command(guard):
    out = guard.run(["init", "reset 1 1", "vel 30 0", "vel 60 0", "lost", "reset 2 1", "vel 300 0"])
    assert out[6] == "30,0 c"                    # HOLD sıfır hız gönderdi: v_önceki = 0


@pytest.mark.parametrize("mm,reason", [(0, Reason.NOT_POSITIVE), (601, Reason.ABOVE_MAX),
                                       (65535, Reason.ABOVE_MAX)])
def test_speed_limit_rejected_with_range(guard, mm, reason):
    _, d = guard.seq("init", "reset 1 1", f"speed 5 {mm}")
    assert rejected(d, Rule.LIMIT, reason) and d.speed is None
    assert (d.value, d.lo, d.hi) == (mm, 1, 600) and d.streak == 1


@pytest.mark.parametrize("mm", [1, 300, 600])
def test_speed_limit_accepted(guard, mm):
    _, d = guard.seq("init", "reset 1 1", f"speed 5 {mm}")
    assert accepted(d) and d.speed == mm and d.goal is None


def test_speed_limit_mode_and_streak(guard):
    ds = guard.seq("init", "speed 1 300",                          # HOLD: MODE, sayılmaz
                   "reset 2 1", "speed 3 900", "goto 4 9000 0 0",   # LIMIT ve GEOFENCE birlikte sayılır
                   "speed 5 300")                                  # kabul: sıfırlar
    assert rejected(ds[0], Rule.MODE, Reason.IN_HOLD) and ds[0].streak == 0
    assert [d.streak for d in ds[2:]] == [1, 2, 0]


def test_fifth_limit_rejection_starts_recovery(guard):
    ds = guard.seq("init", "reset 1 1", *[f"speed {i} 2000" for i in range(2, 7)])
    assert ds[-1].rule == Rule.LIMIT and ds[-1].state == RECOVERY
    assert ds[-1].goal == (*HOME, 0, int(GoalSource.RECOVERY_HOME))


# ---- Tazelik (RULES §3.3, protocol §6.4) ----------------------------------------

def _fresh(guard, type_id, now, ts):
    (out,) = guard.run([f"fresh 7 {type_id} {now} {ts}"])
    return out


@pytest.mark.parametrize("age,ok", [(0, True), (200, True), (201, False), (-50, True), (-51, False)])
def test_freshness_window(guard, age, ok):
    out = _fresh(guard, m.GotoCmd.ID, 100000, 100000 - age)
    assert (out == "1") == ok


@pytest.mark.parametrize("now,ts,ok", [
    (10, 4294967200, True),          # taşma: damga taşmadan 106 ms önce, yaş 106
    (10, 4294967000, False),         # yaş 306
    (4294967290, 20, True),          # damga taşmadan sonra, 26 ms ileride: −26
    (4294967290, 100, False),        # 106 ms ileride
])
def test_freshness_wraparound(guard, now, ts, ok):
    assert (_fresh(guard, m.GotoCmd.ID, now, ts) == "1") == ok


@pytest.mark.parametrize("cls", [m.GotoCmd, m.WaitCmd, m.SpeedLimitCmd, m.StopCmd, m.ResetCmd])
def test_stale_task_command_gets_verdict(guard, cls):
    out = _fresh(guard, cls.ID, 100000, 99500)
    assert out.startswith("0 ") and out != "0 -"
    d = _parse(out[2:])
    assert rejected(d, Rule.FRESHNESS, Reason.TOO_OLD) and d.ref_seq == 7
    assert (d.value, d.lo, d.hi) == (500, -50, 200) and d.halt is None


def test_future_task_command_reason(guard):
    d = _parse(_fresh(guard, m.StopCmd.ID, 100000, 100200)[2:])
    assert rejected(d, Rule.FRESHNESS, Reason.FROM_FUTURE) and d.value == -200


@pytest.mark.parametrize("cls", [m.VelocityCmd, m.Heartbeat])
def test_stale_stream_dropped_silently(guard, cls):
    assert _fresh(guard, cls.ID, 100000, 99000) == "0 -"


def test_freshness_does_not_touch_state_or_streak(guard):
    out = guard.run(["init", "reset 1 1", "goto 2 9000 0 0",
                     f"fresh 3 {m.GotoCmd.ID} 100000 90000", "goto 4 9000 0 0"])
    assert [_parse(out[i]).streak for i in (2, 4)] == [1, 2]       # bayat ret seriye girmedi
    assert _parse(out[4]).state == NORMAL
