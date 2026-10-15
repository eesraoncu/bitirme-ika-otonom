"""Ajanın döngüsü (agent_core.py) doğru mu: sahte model ve sahte dünyayla, ROS ve Ollama'sız.

    python3 -m pytest ros2_ws/src/llm_agent/tests -v
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "tools"))
import agent_core as ac  # noqa: E402
import gen_site as gs  # noqa: E402

PLACES = {"kapi_onu": (26.0, 0.0, 0.0), "kazi_dogu": (20.0, -0.5, math.pi)}


def call(name, **args):
    return {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def say(text):
    return {"content": text}


class FakeChat:
    """Önceden yazılmış cevapları sırayla verir; her çağrıda görülen mesajları saklar."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []

    def __call__(self, messages, tools):
        self.seen.append([dict(m) for m in messages])
        return self.replies.pop(0)


class FakeWorld:
    """observe her çağrıda saati 1 s ilerletir; execute kararları sırayla verir."""

    def __init__(self, *results):
        self.results = list(results)
        self.tasks = []
        self.t = 100.0

    def observe(self):
        self.t += 1.0
        return ac.Observation(1.0, 2.0, self.t)

    def execute(self, task):
        self.tasks.append(task)
        return self.results.pop(0)


def run(chat, world, text="görev", **kw):
    return ac.Agent(chat, world, PLACES, **kw).run(text)


def test_git_by_place_carries_place_heading_and_belief():
    world = FakeWorld((True, "Hedefe varıldı."))
    out = run(FakeChat(call("git", yer="kazi_dogu"), say("Vardım.")), world)
    assert out == {"status": "bitti", "summary": "Vardım.", "steps": 1, "rejections": 0}
    (t,) = world.tasks
    assert (t["cmd"], t["x"], t["y"], t["yaw"], t["yer"]) == ("git", 20.0, -0.5, math.pi, "kazi_dogu")
    # inanç, modeli çağırmadan ÖNCE alınan konum (ilk observe: t = 101)
    assert t["belief"] == {"x": 1.0, "y": 2.0, "stamp": 101.0} and t["id"] == "r1s1"


def test_git_by_coordinates_accepts_turkish_decimal_comma():
    world = FakeWorld((True, "Hedefe varıldı."))
    run(FakeChat(call("git", x="12,5", y=-3), say("tamam")), world)
    assert (world.tasks[0]["x"], world.tasks[0]["y"], world.tasks[0]["yaw"]) == (12.5, -3.0, 0.0)


@pytest.mark.parametrize("reply,expected", [
    (call("bekle", sure_s=30), {"cmd": "bekle", "sure_s": 30.0}),
    (call("hiz_siniri", deger_mps=0.3), {"cmd": "hiz_siniri", "deger_mps": 0.3}),
    (call("dur"), {"cmd": "dur"}),
])
def test_other_tools(reply, expected):
    world = FakeWorld((True, "ok"))
    run(FakeChat(reply, say("bitti")), world)
    t = world.tasks[0]
    assert {k: t[k] for k in expected} == expected
    assert ("belief" in t) == (expected["cmd"] != "dur")       # dur inanç taşımaz (RULES §2)


def test_multi_step_task_and_belief_refreshed_each_step():
    world = FakeWorld((True, "Hedefe varıldı."), (True, "30 saniye beklendi."))
    chat = FakeChat(call("git", yer="kapi_onu"), call("bekle", sure_s=30), say("Kapı önünde bekledim."))
    out = run(chat, world)
    assert out["status"] == "bitti" and out["steps"] == 2
    assert [t["cmd"] for t in world.tasks] == ["git", "bekle"]
    assert world.tasks[1]["belief"]["stamp"] == 102.0           # git'ten sonra yeniden okundu
    # modele sonuç ve yeni konum döndü
    tool_msgs = [m for m in chat.seen[1] if m["role"] == "tool"]
    assert tool_msgs[0]["content"] == "Hedefe varıldı. Aracın şu anki konumu: (1,00; 2,00) m."


def test_rejection_reason_reaches_model_and_correction_is_sent():
    world = FakeWorld((False, "Komut reddedildi (GEOFENCE / GOAL_IN_FORBIDDEN). En yakın güvenli "
                              "nokta: kapi_onu (26,00; 0,00)."), (True, "Hedefe varıldı."))
    chat = FakeChat(call("git", x=14.5, y=0), call("git", yer="kapi_onu"), say("Güvenli noktaya gittim."))
    out = run(chat, world)
    assert out == {"status": "bitti", "summary": "Güvenli noktaya gittim.", "steps": 2, "rejections": 1}
    assert "GOAL_IN_FORBIDDEN" in [m for m in chat.seen[1] if m["role"] == "tool"][0]["content"]


def test_gives_up_after_three_rejections():
    world = FakeWorld(*[(False, "Komut reddedildi.")] * 5)
    chat = FakeChat(*[call("git", x=14.5, y=0)] * 5)
    out = run(chat, world)
    assert out["status"] == "vazgeçti" and out["rejections"] == 3
    assert len(world.tasks) == 3                    # 4. komut karta hiç gitmedi (kart sınırı 5)


def test_invalid_tool_call_not_sent_and_not_counted():
    world = FakeWorld((True, "Hedefe varıldı."))
    chat = FakeChat(call("git", yer="depo_arkasi"), call("ucus"), call("git", yer="kapi_onu"), say("ok"))
    out = run(chat, world)
    assert len(world.tasks) == 1 and out["rejections"] == 0 and out["steps"] == 3
    errs = [m["content"] for m in chat.seen[2] if m["role"] == "tool"]
    assert "kayıtlı bir yer değil" in errs[0] and "diye bir araç yok" in errs[1]


def test_step_limit():
    world = FakeWorld(*[(True, "ok")] * 4)
    out = run(FakeChat(*[call("dur")] * 4), world, max_steps=4)
    assert out["status"] == "adım sınırı" and out["steps"] == 4


def test_places_from_site_merges_safe_points_and_places():
    places = ac.places_from_site(gs.load_site())
    assert places["kapi_onu"] == (26.0, 0.0, 0.0)                  # güvenli nokta, yön 0
    assert places["kazi_dogu"][:2] == (20.0, -0.5)
    assert places["kazi_dogu"][2] == pytest.approx(math.pi, abs=1e-3)
    tools = ac.tool_definitions(sorted(places))
    assert tools[0]["function"]["parameters"]["properties"]["yer"]["enum"] == sorted(places)
    assert [t["function"]["name"] for t in tools] == ["git", "bekle", "hiz_siniri", "dur"]


@pytest.mark.parametrize("args,where", [
    ({"yer": "kapi_onu", "x": 0, "y": 0}, (26.0, 0.0)),            # (0, 0) dolgu: yer
    ({"yer": "kapi_onu", "x": 1.2, "y": 2.3}, (26.0, 0.0)),        # o anki konum (1, 2) ±0,5: yer
    ({"yer": "kapi_onu", "x": 0, "y": 10}, (26.0, 0.0)),           # konuşmada geçmiyor: yer (2026-10-15)
])
def test_git_with_filler_coordinates_uses_place(args, where):
    world = FakeWorld((True, "ok"))
    run(FakeChat(call("git", **args), say("tamam")), world)
    assert (world.tasks[0]["x"], world.tasks[0]["y"]) == where and world.tasks[0]["yer"] == "kapi_onu"


def test_git_with_conflicting_place_and_coordinates_is_not_sent():
    # 2026-10-14 C denemesi: {yer: baslangic, x: 14,5, y: 0}; ajan tahmin etmez, modele sorar
    world = FakeWorld((True, "ok"))
    # Koordinat kullanıcının cümlesinde geçtiği için dolgu değil
    chat = FakeChat(call("git", yer="baslangic", x=14.5, y=0), call("git", x=14.5, y=0), say("tamam"))
    out = run(chat, world, text="Kazı alanının ortasına (14,5; 0) git.")
    assert len(world.tasks) == 1 and world.tasks[0]["x"] == 14.5 and out["rejections"] == 0
    assert "ikisini birden" in [m for m in chat.seen[1] if m["role"] == "tool"][0]["content"]


def test_only_one_coordinate_mentioned_is_filler():
    # "10" bekleme süresi, x ile tesadüfen aynı; y uydurma: nokta konuşmada geçmiyor, yer kullanılır
    world = FakeWorld((True, "ok"))
    run(FakeChat(call("git", yer="kapi_onu", x=10, y=5), say("tamam")), world,
        text="Kapı önüne git, orada 10 saniye bekle.")
    assert (world.tasks[0]["x"], world.tasks[0]["y"]) == (26.0, 0.0)


def test_coordinates_from_card_hint_are_not_filler():
    # Kartın ipucundaki nokta + başka bir yer adı: hangisi kastedildi belli değil, modele sorulur
    hint = ("Komut reddedildi (GEOFENCE / GOAL_IN_FORBIDDEN). Hedef yasak bölgede. "
            "En yakın güvenli nokta: konteyner_onu (8,50; 1,00).")
    world = FakeWorld((False, hint), (True, "ok"))
    chat = FakeChat(call("git", x=14.5, y=0), call("git", yer="kapi_onu", x=8.5, y=1),
                    call("git", x=8.5, y=1), say("tamam"))
    run(chat, world, text="Kazı alanının ortasına (14,5; 0) git.")
    assert [(t["x"], t["y"]) for t in world.tasks] == [(14.5, 0.0), (8.5, 1.0)]
    assert "ikisini birden" in [m for m in chat.seen[2] if m["role"] == "tool"][-1]["content"]


def test_numbers_in_text():
    nums = ac._numbers_in("(8,50; -1) ve x 12,5")
    for want in (8.5, -1.0, 12.5, 8.0, 50.0):
        assert want in nums
    assert ac._numbers_in("Kapı önüne git.") == []
