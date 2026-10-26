"""Match presets: a seed, two teams and the events planted into the match (B04).

`demo-1021` is the recorded demo (PRD section 10): Northgate Rovers lose a player to a red card
at 38', Harbour City take control and lead; at 63' Harbour City take off a winger for a holding
midfielder and drop deeper, and Rovers come back into the game. Only the two planted events
are forced; goals and the turning points come out of the simulation itself. Seed 29 was
picked by scripts/make_demo.py after B12 and B09 (one of 21 in 800) because the alarm fired at
39', 69' and 89' on its own and nowhere else (since B06-opta, the Opta-style momentum: elapsed
37, 66 and 79, shown as 38', 62' and 75'); a04, back at the club he left on bad terms, is
sent off at 38'; Harbour City score at 11', 40' and 52', have a penalty overturned by VAR at
46', and Rovers pull one back at 86': 3-1. (Seed 41 told the story before B12.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain import Match, PlantSpec
from .squads import build_demo_match


@dataclass(frozen=True)
class Preset:
    name: str
    seed: int
    home_strength: float = 72.0
    away_strength: float = 70.0
    home_formation: str = "4-3-3"
    away_formation: str = "4-2-3-1"
    plants: tuple[PlantSpec, ...] = field(default_factory=tuple)
    context_effects: bool = False             # play by the off-pitch context (B14); off until the story is checked

    def build(self, seed: int | None = None) -> Match:
        m = build_demo_match(self.seed if seed is None else seed, self.home_strength, self.away_strength,
                             self.home_formation, self.away_formation)
        return m.model_copy(update={"preset": self.name})


DEMO_PLANTS = (
    PlantSpec(minute=38, type="red_card", team="away", params={"reason": "professional_foul"}),
    # h09 is Harbour City's left winger, h15 the holding midfielder on the bench.
    PlantSpec(minute=63, type="substitution", team="home",
              params={"player_off": "h09", "player_on": "h15", "reason": "tactical",
                      "line_height": "low", "press": "low"}),
)

DEMO_1021 = Preset(name="demo-1021", seed=29, plants=DEMO_PLANTS)

PRESETS = {DEMO_1021.name: DEMO_1021}
