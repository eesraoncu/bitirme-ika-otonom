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

from ika_protocol.messages import BoardState, GoalSource, Reason, Result, Rule   # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc yok")

HOLD, NORMAL = int(BoardState.HOLD), int(BoardState.NORMAL)


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


def _parse(line: str) -> Decision:
    f = line.split()
    goal = None if f[6] == "-" else tuple(int(v) for v in f[6].split(","))
    return Decision(int(f[0]), int(f[1]), int(f[2]), int(f[3]), (int(f[4]), int(f[5])),
                    goal, int(f[7]), int(f[8]))


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
                if c.startswith(("goto", "reset"))]


@pytest.fixture(scope="module")
def guard(tmp_path_factory):
    exe = tmp_path_factory.mktemp("c") / "guard_driver"
    cc = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wsign-conversion",
         "-Werror", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
         "-I", str(APP), "-I", str(PROTO / "c"), str(TESTS / "guard_driver.c"),
         str(APP / "guard" / "guard.c"), str(APP / "site" / "site.c"),
         str(APP / "rules" / "geofence" / "geofence.c"), "-o", str(exe)],
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
    cmds = ["init", "reset 1 1"] + [f"goto {i} 9000 0 0" for i in range(2, 302)]
    ds = guard.seq(*cmds)
    assert ds[-1].streak == 255


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
