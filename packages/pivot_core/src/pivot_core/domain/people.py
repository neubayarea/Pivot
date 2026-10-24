"""Players and coaches: ability ratings, personality, career history and relationships.

The rating set follows the seven groups football games and stats apps use
(attacking, skill, movement, power, mentality, defending, goalkeeping), plus a
hidden personality block in the spirit of manager games. Every person is fictional.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, computed_field

from .common import Model, Side

Rating = Annotated[int, Field(ge=1, le=99)]
Stars = Annotated[int, Field(ge=1, le=5)]

Position = Literal["GK", "DF", "MF", "FW"]

# Detailed role, close to what event providers use. It sets the player's anchor
# point in the formation and which actions they tend to choose.
Role = Literal[
    "GK",
    "LB", "CB", "RB", "LWB", "RWB",
    "DM", "CM", "AM", "LM", "RM",
    "LW", "RW", "ST",
]

ROLE_POSITION: dict[str, Position] = {
    "GK": "GK",
    "LB": "DF", "CB": "DF", "RB": "DF", "LWB": "DF", "RWB": "DF",
    "DM": "MF", "CM": "MF", "AM": "MF", "LM": "MF", "RM": "MF",
    "LW": "FW", "RW": "FW", "ST": "FW",
}

WorkRate = Literal["low", "medium", "high"]


class AttackingAttributes(Model):
    crossing: Rating
    finishing: Rating
    heading_accuracy: Rating
    short_passing: Rating
    volleys: Rating


class SkillAttributes(Model):
    dribbling: Rating
    curve: Rating
    free_kick_accuracy: Rating
    long_passing: Rating
    ball_control: Rating


class MovementAttributes(Model):
    acceleration: Rating
    sprint_speed: Rating
    agility: Rating
    reactions: Rating
    balance: Rating


class PowerAttributes(Model):
    shot_power: Rating
    jumping: Rating
    stamina: Rating
    strength: Rating
    long_shots: Rating


class MentalityAttributes(Model):
    aggression: Rating
    interceptions: Rating
    attack_positioning: Rating
    vision: Rating
    penalties: Rating
    composure: Rating


class DefendingAttributes(Model):
    defensive_awareness: Rating
    standing_tackle: Rating
    sliding_tackle: Rating


class GoalkeepingAttributes(Model):
    diving: Rating
    handling: Rating
    kicking: Rating
    positioning: Rating
    reflexes: Rating


class AttributeSummary(Model):
    """Six headline ratings, weighted from the detailed ones (an approximation of game cards)."""

    pace: int
    shooting: int
    passing: int
    dribbling: int
    defending: int
    physical: int


def _w(*pairs: tuple[float, int]) -> int:
    return round(sum(w * v for w, v in pairs))


class PlayerAttributes(Model):
    """34 visible ratings in seven groups. The simulator reads these directly."""

    attacking: AttackingAttributes
    skill: SkillAttributes
    movement: MovementAttributes
    power: PowerAttributes
    mentality: MentalityAttributes
    defending: DefendingAttributes
    goalkeeping: GoalkeepingAttributes

    @computed_field
    @property
    def summary(self) -> AttributeSummary:
        a, s, m, p, me, d = (self.attacking, self.skill, self.movement, self.power,
                             self.mentality, self.defending)
        return AttributeSummary(
            pace=_w((0.45, m.acceleration), (0.55, m.sprint_speed)),
            shooting=_w((0.05, me.attack_positioning), (0.45, a.finishing), (0.20, p.shot_power),
                        (0.20, p.long_shots), (0.05, a.volleys), (0.05, me.penalties)),
            passing=_w((0.20, me.vision), (0.20, a.crossing), (0.05, s.free_kick_accuracy),
                       (0.35, a.short_passing), (0.15, s.long_passing), (0.05, s.curve)),
            dribbling=_w((0.10, m.agility), (0.05, m.balance), (0.35, s.ball_control),
                         (0.50, s.dribbling)),
            defending=_w((0.20, me.interceptions), (0.10, a.heading_accuracy),
                         (0.30, d.defensive_awareness), (0.30, d.standing_tackle),
                         (0.10, d.sliding_tackle)),
            physical=_w((0.05, p.jumping), (0.25, p.stamina), (0.50, p.strength),
                        (0.20, me.aggression)),
        )


class Personality(Model):
    """Hidden traits. They never show on screen but shape how a player reacts to context."""

    consistency: Rating                       # how much match-to-match form swings
    big_matches: Rating                       # performance in finals, derbies, high-stakes games
    pressure: Rating                          # composure when the game is tight or the crowd hostile
    professionalism: Rating                   # recovery, preparation, behaviour off the pitch
    temperament: Rating                       # low = more likely to lose his head and pick up cards
    ambition: Rating
    loyalty: Rating                           # how strongly he feels about former clubs
    leadership: Rating
    teamwork: Rating
    injury_proneness: Rating
    controversy: Rating                       # likelihood of off-field news


Trait = Literal[
    "finesse_shot", "power_shot", "dead_ball", "chip_shot", "acrobatic",
    "incisive_pass", "long_ball_pass", "whipped_cross", "tiki_taka",
    "rapid", "quick_step", "technical", "trickster", "first_touch",
    "press_proven", "intercept", "block", "bruiser", "slide_tackle", "aerial",
    "relentless", "long_throw", "leader",
]


DepartureMood = Literal["amicable", "neutral", "acrimonious"]


class CareerStint(Model):
    stint_id: str                             # "h07-c2"
    club_id: str
    club_name: str                            # fictional
    from_year: Annotated[int, Field(ge=1980, le=2030)]
    to_year: Annotated[int, Field(ge=1980, le=2030)] | None = None   # None = current club
    as_coach: bool = False
    loan: bool = False
    appearances: Annotated[int, Field(ge=0)] = 0
    goals: Annotated[int, Field(ge=0)] = 0
    departure: Literal["transfer", "loan_end", "released", "contract_end", "sacked", "resigned"] | None = None
    departure_mood: DepartureMood = "neutral"  # acrimonious exits make reunions charged


class Player(Model):
    player_id: str                            # "h07" = home shirt 7, "a11" = away shirt 11
    name: str                                 # fictional, e.g. "R. Okafor"
    team: Side
    shirt_number: Annotated[int, Field(ge=1, le=99)]
    role: Role
    secondary_roles: list[Role] = []
    age: Annotated[int, Field(ge=15, le=45)]
    nationality: str                          # fictional or generic, never tied to a real person
    height_cm: Annotated[int, Field(ge=150, le=210)]
    weight_kg: Annotated[int, Field(ge=50, le=110)]
    preferred_foot: Literal["left", "right"] = "right"
    weak_foot: Stars = 3                      # 5 = equally good with both feet
    skill_moves: Stars = 2
    work_rate_attack: WorkRate = "medium"
    work_rate_defence: WorkRate = "medium"
    attributes: PlayerAttributes
    personality: Personality
    traits: list[Trait] = []
    career: list[CareerStint] = []            # oldest first; the last one is the current club

    @computed_field
    @property
    def position(self) -> Position:
        """Broad position group derived from `role`."""
        return ROLE_POSITION[self.role]


class CoachAttributes(Model):
    tactical_knowledge: Rating
    in_game_adaptability: Rating              # how quickly and how well he reacts during a match
    man_management: Rating
    motivation: Rating


class Coach(Model):
    coach_id: str
    name: str                                 # fictional
    age: Annotated[int, Field(ge=25, le=85)]
    nationality: str
    style: Literal["defensive", "balanced", "attacking"]
    preferred_formation: Annotated[str, Field(pattern=r"^\d(-\d){2,4}$")]
    attributes: CoachAttributes
    personality: Personality
    career: list[CareerStint] = []


RelationshipKind = Literal[
    "former_teammate", "former_coach", "former_player", "mentor", "friend",
    "rival", "feud", "national_teammate",
]


class Relationship(Model):
    """A tie between two people that can matter on match day (chemistry, motivation, needle)."""

    relationship_id: str
    person_id: str                            # player_id or coach_id
    other_id: str
    kind: RelationshipKind
    shared_seasons: Annotated[int, Field(ge=0)] = 0
    sentiment: Annotated[float, Field(ge=-1, le=1)] = 0.0   # -1 bitter, +1 close
