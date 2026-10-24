"""Small hand-made match data shared by the agent tests."""

import pytest

from pivot_worker.testing import FakeStats, event


@pytest.fixture
def events():
    evs = [
        event("m063-s00100", 20),
        event("m063-s01042", 61, "substitution"),
        event("m063-s01077", 62),
        event("m063-s01120", 64, "shot", xg=0.31, shot_outcome="saved"),
        event("m063-s01201", 65, "shot", team="away", xg=0.12, shot_outcome="goal"),
    ]
    return {e.event_id: e for e in evs}


@pytest.fixture
def stats():
    return FakeStats({
        ("passes_final_third", "home", (56, 61)): 3,
        ("passes_final_third", "home", (61, 66)): 9,
        ("pass_accuracy_pct", "home", (56, 61)): 74.2,
        ("pass_accuracy_pct", "home", (61, 66)): 68.4,
        ("xg", "home", (55, 63)): 0.84,
        ("threat_total", "home", (58, 63)): 0.21,
        ("threat_total", "home", (63, 68)): 0.57,
    })
