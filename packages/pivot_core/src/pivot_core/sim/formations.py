"""Formation templates: role and base position of each slot.

Positions are in the team's own view (CONV-002): x from the team's own goal line
(0) towards the opponent's (105), y from the team's right touchline (0) to its left
(68). They describe a mid-block shape; the movement model shifts and stretches it
every second. Slot 1 is the goalkeeper, then back to front, left to right (LineupSlot).
"""

from __future__ import annotations

Slot = tuple[str, float, float]   # role, x, y

FORMATIONS: dict[str, list[Slot]] = {
    "4-3-3": [
        ("GK", 5, 34),
        ("LB", 30, 60), ("CB", 26, 43), ("CB", 26, 25), ("RB", 30, 8),
        ("CM", 52, 46), ("DM", 40, 34), ("CM", 52, 22),
        ("LW", 66, 58), ("ST", 70, 34), ("RW", 66, 10),
    ],
    "4-2-3-1": [
        ("GK", 5, 34),
        ("LB", 30, 60), ("CB", 26, 43), ("CB", 26, 25), ("RB", 30, 8),
        ("DM", 40, 42), ("DM", 40, 26),
        ("LW", 60, 56), ("AM", 58, 34), ("RW", 60, 12),
        ("ST", 70, 34),
    ],
    "4-4-2": [
        ("GK", 5, 34),
        ("LB", 30, 60), ("CB", 26, 43), ("CB", 26, 25), ("RB", 30, 8),
        ("LM", 46, 58), ("CM", 44, 41), ("CM", 44, 27), ("RM", 46, 10),
        ("ST", 66, 41), ("ST", 66, 27),
    ],
    "4-1-4-1": [
        ("GK", 5, 34),
        ("LB", 30, 60), ("CB", 26, 43), ("CB", 26, 25), ("RB", 30, 8),
        ("DM", 38, 34),
        ("LM", 52, 58), ("CM", 50, 42), ("CM", 50, 26), ("RM", 52, 10),
        ("ST", 68, 34),
    ],
    "3-5-2": [
        ("GK", 5, 34),
        ("CB", 26, 50), ("CB", 24, 34), ("CB", 26, 18),
        ("LWB", 46, 62), ("CM", 44, 44), ("DM", 38, 34), ("CM", 44, 24), ("RWB", 46, 6),
        ("ST", 66, 41), ("ST", 66, 27),
    ],
    "5-4-1": [
        ("GK", 5, 34),
        ("LWB", 30, 62), ("CB", 24, 48), ("CB", 22, 34), ("CB", 24, 20), ("RWB", 30, 6),
        ("LM", 44, 56), ("CM", 42, 40), ("CM", 42, 28), ("RM", 44, 12),
        ("ST", 62, 34),
    ],
}

DEFENDER_ROLES = {"LB", "CB", "RB", "LWB", "RWB"}
MIDFIELD_ROLES = {"DM", "CM", "AM", "LM", "RM"}
WIDE_DEFENDERS = {"LB", "RB", "LWB", "RWB"}
