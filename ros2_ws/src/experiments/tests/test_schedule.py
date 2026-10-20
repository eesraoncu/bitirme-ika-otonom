"""Tam deneyin sırası ve parça parça koşulması (schedule.py).

    python3 -m pytest ros2_ws/src/experiments/tests -v
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import schedule as sch  # noqa: E402

LLM = {"id": "normal_1", "category": "normal"}
FREEZE = {"id": "agent_freeze_1", "category": "agent_freeze"}
LINK = {"id": "link_loss_1", "category": "link_loss", "configs": ["C", "D"]}


@pytest.mark.parametrize("text, expected", [("1", [1]), ("1-3", [1, 2, 3]), ("1,4", [1, 4]),
                                            ("1-2,7", [1, 2, 7])])
def test_seeds(text, expected):
    assert sch.seeds(text) == expected


def test_order_is_repetition_first():
    order = [(s["id"], c, n) for s, c, n in sch.run_order([LLM, FREEZE], "AB", [1, 2])]
    assert order == [("normal_1", "A", 1), ("normal_1", "B", 1), ("agent_freeze_1", "A", 1),
                     ("agent_freeze_1", "B", 1), ("normal_1", "A", 2), ("normal_1", "B", 2),
                     ("agent_freeze_1", "A", 2), ("agent_freeze_1", "B", 2)]


def test_infra_stops_at_ten_and_respects_configs():
    order = sch.run_order([LLM, FREEZE, LINK], "ABCD", sch.seeds("1-15"))
    count = lambda sid: sum(1 for s, _, _ in order if s["id"] == sid)  # noqa: E731
    assert (count("normal_1"), count("agent_freeze_1"), count("link_loss_1")) == (60, 40, 20)
    assert {c for s, c, _ in order if s["id"] == "link_loss_1"} == {"C", "D"}


def test_full_experiment_size():
    # K-066: 12 LLM senaryosu × 4 × 15 + donma 4 × 10 + kablo 2 × 10 = 780
    specs = [{"id": f"llm{i}", "category": "normal"} for i in range(12)] + [FREEZE, LINK]
    assert len(sch.run_order(specs, "ABCD", sch.seeds("1-15"))) == 780


def test_done_keys_skip():
    rows = [{"senaryo": "normal_1", "yapilandirma": "A", "tekrar": "1"}]
    done = sch.done_keys(rows)
    assert ("normal_1", "A", "1") in done and ("normal_1", "A", "2") not in done


@pytest.mark.parametrize("row, bad", [
    ({"kart_hold": "True", "kurtarma": "False", "sim_hiz_orani": "1.0", "olay": ""}, True),
    ({"kart_hold": "True", "kurtarma": "True", "sim_hiz_orani": "1.0", "olay": ""}, False),  # kurtarmanın sonu
    ({"kart_hold": "", "kurtarma": "", "sim_hiz_orani": "0.85", "olay": ""}, True),
    ({"kart_hold": "", "kurtarma": "", "sim_hiz_orani": "0.95", "olay": ""}, False),
    ({"kart_hold": "False", "kurtarma": "False", "sim_hiz_orani": "", "olay": "olmadı"}, True),
    ({"kart_hold": "False", "kurtarma": "False", "sim_hiz_orani": "1.0", "olay": "oldu"}, False),
])
def test_invalid(row, bad):
    assert bool(sch.invalid(row)) is bad


def test_deadline_next_morning():
    night = dt.datetime(2026, 10, 20, 22, 30)
    assert sch.deadline("08:00", night) == dt.datetime(2026, 10, 21, 8, 0)
    morning = dt.datetime(2026, 10, 21, 6, 0)
    assert sch.deadline("08:00", morning) == dt.datetime(2026, 10, 21, 8, 0)
