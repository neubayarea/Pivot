"""Referees, fouls, cards, VAR reviews and injuries. All officials are fictional."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Model
from .people import Rating


class Referee(Model):
    referee_id: str
    name: str                                 # fictional
    strictness: Rating                        # how readily he whistles for contact
    card_tendency: Rating                     # how readily a foul becomes a card
    advantage_tendency: Rating                # how often he lets play run after a foul
    big_match_experience: Rating


FoulType = Literal[
    "tackle", "trip", "push", "hold", "handball", "dangerous_play", "obstruction",
    "simulation", "dissent", "time_wasting", "off_the_ball",
]

CardType = Literal["yellow", "second_yellow", "red"]
CardReason = Literal[
    "reckless_challenge", "serious_foul_play", "professional_foul", "denying_goal_chance",
    "handball", "dissent", "simulation", "time_wasting", "violent_conduct", "persistent_fouling",
]


class FoulDetail(Model):
    foul_type: FoulType
    advantage_played: bool = False            # referee let play continue
    penalty_awarded: bool = False
    card: CardType | None = None              # shown for this foul, if any
    card_reason: CardReason | None = None


class VarReview(Model):
    review_of: Literal["goal", "penalty", "red_card", "mistaken_identity"]
    reviewed_event_id: str
    decision: Literal["confirmed", "overturned"]
    reason: Literal[
        "offside", "handball", "foul_in_build_up", "ball_out_of_play", "no_foul", "foul_confirmed",
        "wrong_player", "clear_and_obvious_error",
    ]
    duration_s: Annotated[int, Field(ge=0, le=600)] = 60


InjuryArea = Literal[
    "hamstring", "groin", "thigh", "knee", "ankle", "calf", "foot", "back", "shoulder", "head", "other",
]


class InjuryInfo(Model):
    area: InjuryArea
    severity: Literal["knock", "minor", "moderate", "serious"]
    cause: Literal["contact", "non_contact", "fatigue"]
    can_continue: bool                        # knocks usually can; anything else means a substitution
    expected_days_out: Annotated[int, Field(ge=0, le=400)] = 0
