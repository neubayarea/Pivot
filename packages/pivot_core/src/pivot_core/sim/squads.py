"""Minimal squad and match builder for the simulator.

This is a stand-in for the fictional world generator (B13): it creates two teams with
role-appropriate ratings, a team sheet from a formation template and default tactics.
All names are generated and fictional.
"""

from __future__ import annotations

import numpy as np

from ..domain import (
    Coach, Competition, LineupSlot, Match, MatchContext, Personality, Player, PlayerAttributes,
    Referee, Team, TeamSheet, TeamTactics,
)
from .formations import FORMATIONS
from .movement import normal

_SYLLABLES = ["ka", "ro", "vel", "sen", "dar", "mi", "to", "la", "ber", "quin", "ras", "no",
              "fel", "gor", "li", "an", "tes", "mor", "hal", "vik", "do", "ren", "sa", "bel"]
_ENDINGS = ["", "son", "ez", "ini", "ov", "er", "sen", "a", "o", "is"]

# Rating offsets by role, relative to the team's strength. Keys are rating names.
_ROLE_BIAS: dict[str, dict[str, int]] = {
    "GK": {"diving": 18, "handling": 16, "kicking": 8, "positioning": 16, "reflexes": 18,
           "finishing": -40, "dribbling": -30, "crossing": -30, "volleys": -40, "heading_accuracy": -20,
           "standing_tackle": -30, "sliding_tackle": -30, "defensive_awareness": -15, "sprint_speed": -15,
           "acceleration": -15, "long_shots": -35, "curve": -20, "free_kick_accuracy": -20},
    "CB": {"defensive_awareness": 12, "standing_tackle": 12, "sliding_tackle": 10, "heading_accuracy": 10,
           "strength": 10, "jumping": 8, "interceptions": 8, "finishing": -25, "dribbling": -12,
           "crossing": -15, "curve": -12, "volleys": -20, "long_shots": -18, "agility": -6},
    "FB": {"sprint_speed": 6, "acceleration": 6, "stamina": 8, "crossing": 6, "standing_tackle": 6,
           "defensive_awareness": 4, "finishing": -18, "heading_accuracy": -4, "volleys": -15},
    "DM": {"interceptions": 10, "defensive_awareness": 8, "standing_tackle": 8, "short_passing": 6,
           "stamina": 6, "aggression": 6, "finishing": -12, "dribbling": -4},
    "CM": {"short_passing": 9, "long_passing": 8, "vision": 8, "stamina": 8, "ball_control": 6,
           "finishing": -6, "standing_tackle": -2},
    "AM": {"vision": 12, "short_passing": 8, "dribbling": 9, "ball_control": 9, "agility": 6,
           "finishing": 2, "curve": 6, "defensive_awareness": -14, "standing_tackle": -14},
    "W": {"sprint_speed": 12, "acceleration": 12, "dribbling": 10, "agility": 9, "crossing": 7,
          "ball_control": 6, "defensive_awareness": -18, "standing_tackle": -16, "strength": -6},
    "ST": {"finishing": 14, "attack_positioning": 12, "heading_accuracy": 6, "shot_power": 8,
           "composure": 6, "volleys": 8, "defensive_awareness": -22, "standing_tackle": -20,
           "sliding_tackle": -22, "interceptions": -15},
}
_ROLE_GROUP = {"GK": "GK", "CB": "CB", "LB": "FB", "RB": "FB", "LWB": "FB", "RWB": "FB",
               "DM": "DM", "CM": "CM", "LM": "W", "RM": "W", "AM": "AM", "LW": "W", "RW": "W", "ST": "ST"}

_GROUPS = {
    "attacking": ["crossing", "finishing", "heading_accuracy", "short_passing", "volleys"],
    "skill": ["dribbling", "curve", "free_kick_accuracy", "long_passing", "ball_control"],
    "movement": ["acceleration", "sprint_speed", "agility", "reactions", "balance"],
    "power": ["shot_power", "jumping", "stamina", "strength", "long_shots"],
    "mentality": ["aggression", "interceptions", "attack_positioning", "vision", "penalties", "composure"],
    "defending": ["defensive_awareness", "standing_tackle", "sliding_tackle"],
    "goalkeeping": ["diving", "handling", "kicking", "positioning", "reflexes"],
}


def _name(rng: np.random.Generator) -> str:
    surname = "".join(rng.choice(_SYLLABLES, size=rng.integers(2, 4))) + rng.choice(_ENDINGS)
    return f"{chr(65 + rng.integers(0, 26))}. {surname.capitalize()}"


def _attributes(rng: np.random.Generator, role: str, strength: float) -> PlayerAttributes:
    bias = _ROLE_BIAS[_ROLE_GROUP[role]]
    groups = {}
    for group, names in _GROUPS.items():
        out = {}
        for n in names:
            base = strength + bias.get(n, 0)
            if group == "goalkeeping" and role != "GK":
                base = 12
            out[n] = int(np.clip(round(base + normal(rng, 0, 5)), 5, 97))
        groups[group] = out
    return PlayerAttributes(**groups)


def _personality(rng: np.random.Generator) -> Personality:
    return Personality(**{f: int(np.clip(round(normal(rng, 60, 14)), 5, 95)) for f in Personality.model_fields})


_BENCH_ROLES = ["GK", "CB", "LB", "DM", "CM", "RW", "ST"]


def build_team(rng: np.random.Generator, side: str, club_id: str, name: str, short: str, color: str,
               formation: str = "4-3-3", strength: float = 70.0,
               tactics: TeamTactics | None = None) -> Team:
    prefix = side[0]
    template = FORMATIONS[formation]
    squad: list[Player] = []
    starters: list[LineupSlot] = []
    shirt = 1
    for slot, (role, ax, ay) in enumerate(template, start=1):
        pid = f"{prefix}{shirt:02d}"
        squad.append(Player(player_id=pid, name=_name(rng), team=side, shirt_number=shirt, role=role,
                            age=int(rng.integers(19, 34)), nationality="Freeland",
                            height_cm=int(normal(rng, 181, 6)), weight_kg=int(normal(rng, 76, 6)),
                            preferred_foot="left" if role in {"LB", "LWB", "LW", "LM"} and rng.random() < 0.6
                            else ("left" if rng.random() < 0.2 else "right"),
                            attributes=_attributes(rng, role, strength + normal(rng, 0, 3)),
                            personality=_personality(rng)))
        starters.append(LineupSlot(player_id=pid, slot=slot, role=role, anchor=(ax, ay)))
        shirt += 1
    bench = []
    for role in _BENCH_ROLES:
        pid = f"{prefix}{shirt:02d}"
        squad.append(Player(player_id=pid, name=_name(rng), team=side, shirt_number=shirt, role=role,
                            age=int(rng.integers(18, 34)), nationality="Freeland",
                            height_cm=int(normal(rng, 181, 6)), weight_kg=int(normal(rng, 76, 6)),
                            attributes=_attributes(rng, role, strength - 3 + normal(rng, 0, 3)),
                            personality=_personality(rng)))
        bench.append(pid)
        shirt += 1
    ids = [s.player_id for s in starters]
    by_role = {s.role: s.player_id for s in starters}
    sheet = TeamSheet(formation=formation, starters=starters, bench=bench, captain_id=ids[5],
                      penalty_taker_id=by_role.get("ST", ids[-1]), free_kick_taker_id=ids[6],
                      corner_taker_left_id=ids[-3], corner_taker_right_id=ids[-1])
    coach = Coach(coach_id=f"{prefix}-coach", name=_name(rng), age=int(rng.integers(38, 66)),
                  nationality="Freeland", style="balanced", preferred_formation=formation,
                  attributes={"tactical_knowledge": 70, "in_game_adaptability": 65,
                              "man_management": 65, "motivation": 68},
                  personality=_personality(rng))
    return Team(side=side, club_id=club_id, name=name, short_name=short, color=color, coach=coach,
                squad=squad, sheet=sheet, tactics=tactics or TeamTactics())


def build_demo_match(seed: int, home_strength: float = 72.0, away_strength: float = 70.0,
                     home_formation: str = "4-3-3", away_formation: str = "4-2-3-1") -> Match:
    rng = np.random.default_rng(seed)
    home = build_team(rng, "home", "club-hbc", "Harbour City", "HBC", "#1E6B45", home_formation, home_strength)
    away = build_team(rng, "away", "club-rov", "Northgate Rovers", "ROV", "#4A1D57", away_formation, away_strength)
    context = MatchContext(
        competition=Competition(competition_id="fl-1", name="Freeland League", level="league", importance=2),
        venue="Harbour Park", attendance=38000,
        referee=Referee(referee_id="ref-1", name=_name(rng), strictness=60, card_tendency=60,
                        advantage_tendency=55, big_match_experience=60),
    )
    return Match(match_id=f"M-seed-{seed}", seed=seed, home=home, away=away, context=context, status="scheduled")
