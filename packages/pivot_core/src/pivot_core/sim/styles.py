"""Coach styles (Bx13): each side of a simulated match gets a way of playing, so the two coaches'
plans differ from match to match instead of every team playing the default tactics.

`with_coach_styles(match)` picks a style for each coach from the match's seed (its own random
stream, so squads, names and ratings stay exactly as `build_demo_match` made them) and sets the
coach's `style` and the team's tactics and set-piece plan from it. The tactics feed the simulator,
so a match played with styles has other results than the same seed without them.
"""

from __future__ import annotations

import numpy as np

from ..domain import Match, SetPieceTactics, Team, TeamTactics

# name: (coach style, tactics, set-piece plan). Only what the simulator reads differs from the default:
# press, line height, width, tempo, passing, and the set-piece numbers and schemes.
STYLES: dict[str, tuple[str, dict, dict]] = {
    "high_press": ("attacking",
                   dict(press="high", line_height="high", tempo="fast", passing="short", width="normal"),
                   dict(corner_delivery="inswing", corner_target="near_post", players_forward_on_corners=6,
                        corner_defence="zonal", players_back_on_corners=1)),
    "possession": ("attacking",
                   dict(press="mid", line_height="high", tempo="slow", passing="short", width="wide"),
                   dict(corner_delivery="short", corner_target="edge_of_box", free_kick_style="short",
                        players_forward_on_corners=4, corner_defence="mixed", players_back_on_corners=2)),
    "direct": ("balanced",
               dict(press="mid", line_height="mid", tempo="fast", passing="direct", width="normal"),
               dict(corner_delivery="outswing", corner_target="far_post", free_kick_style="cross",
                    players_forward_on_corners=6, corner_defence="man", players_back_on_corners=1)),
    "counter": ("defensive",
                dict(press="low", line_height="low", tempo="fast", passing="direct", width="normal",
                     counter_attack=True),
                dict(corner_delivery="mixed", corner_target="penalty_spot", players_forward_on_corners=4,
                     corner_defence="zonal", players_back_on_corners=2)),
    "deep_block": ("defensive",
                   dict(press="low", line_height="low", tempo="slow", passing="mixed", width="narrow"),
                   dict(corner_delivery="inswing", corner_target="penalty_spot", free_kick_style="direct",
                        players_forward_on_corners=5, corner_defence="zonal", players_back_on_corners=1)),
    "balanced": ("balanced", {}, {}),
}
STYLE_SEED = 51                               # the style's own stream, next to the match seed


def style_of(seed: int, side: str) -> str:
    rng = np.random.default_rng([seed, STYLE_SEED, 0 if side == "home" else 1])
    names = list(STYLES)
    return names[int(rng.integers(len(names)))]


def with_style(team: Team, style: str) -> Team:
    coach_style, tactics, set_pieces = STYLES[style]
    tac = TeamTactics(**tactics, set_pieces=SetPieceTactics(**set_pieces), instructions=team.tactics.instructions)
    coach = team.coach.model_copy(update={"style": coach_style})
    return team.model_copy(update={"tactics": tac, "coach": coach})


def with_coach_styles(match: Match) -> Match:
    """Both coaches' styles from the match seed, applied to the teams before kick-off."""
    return match.model_copy(update={side: with_style(getattr(match, side), style_of(match.seed, side))
                                    for side in ("home", "away")})
