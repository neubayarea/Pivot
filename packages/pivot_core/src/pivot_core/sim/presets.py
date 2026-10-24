"""Match presets: a seed, two teams and the events planted into the match (B04).

`demo-1021` is the recorded demo (PRD section 10): Northgate Rovers lose a player to a red card
at 38', Harbour City take control and lead; at 63' Harbour City take off a winger for a holding
midfielder and drop deeper, and Rovers come back into the game. Only the two planted events
are forced; goals and the turning points come out of the simulation itself. Seed 41 was
picked by scripts/make_demo.py (one of 4 in 600) because the alarm fires at 38' and 65' on its
own; Harbour City win 1-0 on 14 shots to 5.
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

DEMO_1021 = Preset(name="demo-1021", seed=41, plants=DEMO_PLANTS)

PRESETS = {DEMO_1021.name: DEMO_1021}
