"""Per-second positional match engine (B03, ADR-0014).

Every second:

1. the player on the ball (if any) chooses an action from his position, the pressure on
   him, his ratings and the team's tactics: hold and carry, pass, dribble, shoot; nearby
   defenders may tackle or foul;
2. passes and shots are resolved with probabilities that depend on the positions of all
   22 players (lane interceptions, tight marking, blockers, the keeper);
3. the ball goes out of play, is restarted, or is lost and recovered;
4. the movement model (movement.py) moves everyone one second;
5. one tracking frame is recorded.

Events are built as plain dicts while the match runs and converted to the shared models at
the end (`SimOutput.events_as_models`). Field meanings follow docs/data-definitions.md; the
comment next to each rule names the definition it implements.

Realism rules (game state, keepers, injuries, VAR, extra time and shootouts) are described in
docs/sim-realism.md (B12). The context effects (B14, CTX-001) apply only with
`Params.context_effects` (or `simulate(..., context_effects=True)`): each player's effects are
summed at kick-off and act as small factors on rates the engine already has (see `_effects`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from ..domain import (
    FoulDetail, InjuryInfo, LineupSlot, Match, MatchEvent, PeriodInfo, PlantSpec, Score, Substitution, TeamSheet,
    TrackingFrame, VarReview,
)
from ..domain.common import PERIOD_BASE_MINUTE, PERIOD_LENGTH_MINUTES, PITCH_LENGTH, PITCH_WIDTH, zone_of
from .effects import context_effects as context_effects_of
from .formations import DEFENDER_ROLES, FORMATIONS, MIDFIELD_ROLES
from .movement import (
    ACCEL_MS2, BURST_S, RECOVER_MS, RECOVERED_S, SPRINT_MS, MovementModel, TeamShape, clip1, from_view, norm,
    normal, settle, to_view, top_speed, uniform,
)
from .setpieces import KEEP_OFF, SetPieceShape

GOAL = np.array([PITCH_LENGTH, PITCH_WIDTH / 2])
BOX_DEPTH, BOX_Y = 16.5, (13.84, 54.16)
PRESS_RADIUS, PRESS_RADIUS_GK = 4.6, 9.1          # EVT-006
CLOSE_RADIUS, CLOSING_SPEED = 2.0, 1.0            # ATTR-001
SIDES = ("home", "away")
URGENCY_LEAD = (-1.0, -0.7, -0.4)                # ahead by 1, 2, 3+ (REAL-001)
URGENCY_TRAIL = (1.0, 0.8, 0.3)                  # behind by 1, 2, 3+: a lost cause is chased less
# Injuries (REAL-010): how bad, where, and roughly how long out. Only a knock lets him play on.
SEVERITY = (("knock", 0.80), ("minor", 0.10), ("moderate", 0.07), ("serious", 0.03))
INJURY_AREAS = {"contact": ("ankle", "knee", "thigh", "foot", "head", "shoulder", "other"),
                "non_contact": ("hamstring", "groin", "calf", "thigh", "back"),
                "fatigue": ("hamstring", "calf", "groin")}
DAYS_OUT = {"knock": (0, 1), "minor": (3, 11), "moderate": (14, 43), "serious": (60, 241)}
# Stoppage time per period (REAL-012): base minutes and the range the board can show.
ADDED_BASE = {1: 1.0, 2: 3.0, 3: 0.5, 4: 1.0}
ADDED_RANGE = {1: (1, 4), 2: (3, 8), 3: (0, 3), 4: (1, 4)}
SUB_LIMIT = (5, 6)                               # changes per side in normal time; one more in extra time
RECEIVE_REACH = 6.0                              # metres: a receiver this close collects the ball where he is
LATE_S = 3                                       # seconds a ball waits for a receiver still running onto it
RUNNERS = ("ST", "LW", "RW", "AM", "LM", "RM")   # who gets balls played into space behind the line (REAL-016)
CLAIM_REACH = 4.5                                # metres a keeper can reach for a cross
URGENT_GAP = 20.0                                # metres out of position: he sprints back (REAL-014)
HALVES = ((1, 0), (2, 1))                         # period, side kicking off
FORWARD = ("ST", "LW", "RW", "AM")

# Scoring chance by shot technique relative to a normal strike from the same spot (ATTR-014):
# volleys and acrobatic finishes are harder to keep down and on target, a lob over a keeper
# who has come off his line is easier. Weighted over the mix of shots the average stays near 1.
TECHNIQUE_XG = {"normal": 1.02, "half_volley": 0.9, "volley": 0.8, "lob": 1.3, "backheel": 0.6,
                "diving_header": 1.0, "overhead_kick": 0.55}

# Foot-shot technique by how the shooter last got the ball and whether he struck it first time,
# counted from StatsBomb open data, 2022 World Cup (64 matches, 1,178 foot shots without
# penalties); the rest of each row is "normal". "loose" covers rebounds, loose balls and
# balls won off an opponent. Headers: 5.6 % diving headers.
SHOT_TECHNIQUE_MIX = {
    ("high", True): (("volley", 0.53), ("half_volley", 0.355), ("overhead_kick", 0.065), ("backheel", 0.03)),
    ("low", True): (("half_volley", 0.73), ("volley", 0.125), ("backheel", 0.04)),
    ("ground", True): (("half_volley", 0.047), ("lob", 0.016), ("volley", 0.01)),
    ("loose", True): (("half_volley", 0.42), ("volley", 0.23), ("overhead_kick", 0.012), ("backheel", 0.006),
                      ("lob", 0.006)),
    ("high", False): (("half_volley", 0.34), ("volley", 0.04), ("lob", 0.012)),
    ("low", False): (("half_volley", 0.18), ("volley", 0.02)),
    ("ground", False): (("half_volley", 0.032), ("lob", 0.011), ("volley", 0.003), ("overhead_kick", 0.003)),
    ("loose", False): (("half_volley", 0.14), ("volley", 0.04), ("lob", 0.02)),
}
DIVING_HEADER_SHARE = 0.056
FINISH_WEIGHT = 1.2               # xG x (1 + FINISH_WEIGHT * (finishing - 0.7)): a 90 finisher gets 1.24
# The engine decides once a second, so "his first decision after the ball arrived" also
# catches a quick touch and pass inside that second. Only this share of those passes is
# recorded as first time, which brings one-touch passes to the 16 % StatsBomb shows
# (no carry between receiving and passing).
FIRST_TIME_PASS_SHARE = 0.37
CLOSE_IN_XG = 0.15               # below this, a player in space carries on towards goal rather than shoot (REAL-017)
# A counter-attack (ATTR-003) has to reach the opponents' box within 9 s of winning the ball in
# the own half. That gives about 3.5 a match, as StatsBomb's Premier League 2015/16 labels do.
COUNTER_REACH, COUNTER_SECONDS = PITCH_LENGTH - BOX_DEPTH, 9


@dataclass
class Params:
    """Tunable rates. First guesses, to be calibrated in B07."""

    pass_rate: dict = field(default_factory=lambda: {"slow": 0.28, "normal": 0.34, "fast": 0.42})
    pass_rate_pressed: float = 0.30
    tackle_attempt: float = 0.17
    foul_rate: float = 0.27
    yellow_rate: float = 0.15
    red_rate: float = 0.00243
    shot_base: float = 0.0
    shot_xg_weight: float = 2.2
    shot_min_xg: float = 0.04
    block_base: float = 0.22
    block_per_defender: float = 0.12
    saved_share: float = 0.33
    post_share: float = 0.05
    home_boost: float = 1.05                     # CTX-003, scaled by attendance in _success
    long_shot_rate: float = 0.02                 # per second on the ball 18-32 m out, scaled by long_shots
    # Game state (B12, REAL-001): urgency runs from -1 (protecting a lead late on) to +1 (chasing it).
    state_line: float = 1.56                     # back-line shift in metres at full urgency, out of possession
    state_press_at: float = 0.8                  # urgency beyond which a side presses one level higher or lower
    man_line: float = 2.0                        # back-line shift per player more (+) or fewer (-) on the pitch
    state_shot: float = 0.208                    # shot willingness x (1 + state_shot * urgency)
    state_direct: float = 0.35                   # long-pass penalty x (1 - state_direct * urgency) when chasing
    waste_s: float = 13.73                       # extra seconds the leading side takes over its restarts
    # Chance creation (B12).
    lane_cut: float = 0.084                      # cut-out chance for an opponent right on the passing lane
    intercept_share: float = 0.451               # cut-outs recorded as interceptions; the rest are recoveries
    high_pass_acc: float = 0.85                  # accuracy factor for a ball in the air (low passes: halfway)
    clear_under_pressure: float = 0.407          # a defender pressed near his own goal clears it
    clear_behind: float = 0.366                  # a clearance in his own box goes behind for a corner
    loose_shot: float = 0.1                      # chance to strike a loose ball in front of goal first time, x (1 + 8 xG)
    offside_pen: float = 3.2                     # passer's reluctance to pick a receiver standing offside
    corner_line_pen: float = 2.2                 # corner taker's reluctance to aim within 4 m of the goal line (Ax44)
    offside_slack: float = 1.1                   # metres a forward may drift beyond the last defender
    claim_rate: float = 0.9                      # keeper comes for a cross dropping into his area
    sweep_rate: float = 0.13                     # keeper rushes out to a ball played in behind
    through_lead: float = 0.8                    # a runner level with the line gets the ball into space behind it
    close_in: float = 0.5                        # shot willingness when free and the chance can still get better
    aerial_contest: float = 4.91                 # metres: a defender this close to a long ball's drop challenges for it
    line_lift: float = 2.5                       # metres added to every team's line height (REAL-015)
    pass_forward: float = 0.043                  # pass choice: weight per metre gained towards goal
    pass_threat: float = 20.0                    # pass choice: weight on threat gained
    # Fatigue, injuries, VAR (B12).
    fatigue_err: float = 0.347                   # pass accuracy x (1 - fatigue_err * (1 - fitness)); duels alike
    injury_foul: float = 0.127                   # the fouled player is hurt
    injury_sprint: float = 0.0003                # per second sprinting, x (1.3 - fitness): a pulled muscle
    var_check: float = 0.25                      # a goal gets a visible VAR check (and stands)
    var_pen_overturn: float = 0.2                # a penalty given is overturned on review
    var_pen_award: float = 0.04                  # a tackle won in the box is reviewed and given as a penalty
    var_disallow: float = 0.047                  # a goal is ruled out by VAR (offside, a foul, handball)
    # How much the ratings matter (B12): a better side should win more often.
    skill_pass: float = 0.6                      # pass accuracy x (1 + skill_pass * (passing - 0.75))
    skill_def: float = 1.0                       # lane cut-out x (1 + skill_def * (interceptions - 0.7))
    skill_gk: float = 0.827                      # goal chance x (1 - skill_gk * (keeper - 0.88))
    # Off-pitch context (B14, CTX-001): play by match.context.effects. Off by default, so every seed
    # plays exactly as before until the demo story is checked with it on.
    context_effects: bool = False


@dataclass
class SimOutput:
    match: Match
    events: list[dict]
    frames_t: np.ndarray                          # (n,) elapsed seconds
    frames_period: np.ndarray
    frames_possession: np.ndarray                 # -1 dead ball, 0 home, 1 away
    frames_ball: np.ndarray                       # (n, 3)
    frames_owner: list[str | None]
    frames_ids: list[list[list[str | None]]]      # per frame, per team, 11 slots
    frames_pos: np.ndarray                        # (n, 2, 11, 2)
    frames_speed: np.ndarray                      # (n, 2, 11)
    frames_fitness: np.ndarray                    # (n, 2, 11)

    def events_as_models(self) -> list[MatchEvent]:
        return [MatchEvent.model_validate({k: v for k, v in e.items() if not k.startswith("_")})
                for e in self.events]

    def frames_as_models(self) -> list[TrackingFrame]:
        out = []
        for n, t in enumerate(self.frames_t):
            players = []
            for k in (0, 1):
                for i, pid in enumerate(self.frames_ids[n][k]):
                    if pid:
                        x, y = self.frames_pos[n, k, i]
                        players.append({"player_id": pid, "x": round(float(x), 1), "y": round(float(y), 1),
                                        "speed_ms": round(float(self.frames_speed[n, k, i]), 2),
                                        "fitness": round(float(self.frames_fitness[n, k, i]), 3)})
            p = int(self.frames_possession[n])
            bx, by, bz = self.frames_ball[n]
            out.append(TrackingFrame(match_id=self.match.match_id, t=int(t), period=int(self.frames_period[n]),
                                     possession=None if p < 0 else SIDES[p],
                                     ball={"x": round(float(bx), 1), "y": round(float(by), 1),
                                           "z": round(float(bz), 2), "owner_id": self.frames_owner[n]},
                                     players=players))
        return out


def xg_model(v: np.ndarray, header: bool = False, blockers: int = 0, pressed: bool = False,
             finishing: float = 0.7) -> float:
    """Scoring probability of a shot from team-view position v (ATTR-008)."""
    dx, dy = PITCH_LENGTH - v[0], v[1] - PITCH_WIDTH / 2
    d = math.sqrt(dx * dx + dy * dy)
    half = 7.32 / 2
    angle = math.atan2(7.32 * max(dx, 0.1), dx * dx + dy * dy - half * half)
    if angle < 0:
        angle += math.pi
    p = 1 / (1 + math.exp(-(-1.9 + 1.95 * angle - 0.085 * d)))
    if header:
        p *= 0.55
    p *= 0.8 ** blockers
    if pressed:
        p *= 0.85
    p *= 1 + FINISH_WEIGHT * (finishing - 0.7)
    return float(np.clip(p, 0.005, 0.95))


def threat_value(v: np.ndarray) -> float:
    """Placeholder expected-threat surface until B05 learns the 16 x 12 grid (ATTR-009)."""
    dx, dy = PITCH_LENGTH - v[0], (v[1] - PITCH_WIDTH / 2) * 1.4
    d = math.sqrt(dx * dx + dy * dy)
    return 0.004 + 0.32 * math.exp(-d / 11.0)


def _in_box(v: np.ndarray) -> bool:
    """Opponent's penalty box, team view."""
    return v[0] >= PITCH_LENGTH - BOX_DEPTH and BOX_Y[0] <= v[1] <= BOX_Y[1]


def _in_own_box(v: np.ndarray) -> bool:
    return v[0] <= BOX_DEPTH and BOX_Y[0] <= v[1] <= BOX_Y[1]


class Engine:
    def __init__(self, match: Match, seed: int | None = None, params: Params | None = None,
                 plants: list[PlantSpec] | None = None, context_effects: bool | None = None):
        params = params or Params()
        if context_effects is not None and context_effects != params.context_effects:
            params = replace(params, context_effects=context_effects)
        if params.context_effects:
            # CTX-001: the effects are worked out before kick-off and recorded with the match
            effects = match.context.effects or context_effects_of(match)
            match = match.model_copy(update={"context": match.context.model_copy(update={"effects": effects})})
        self.match = match
        # Planted events (B04): forced at a given minute, e.g. the demo's 38' red card.
        self.plants = [{"spec": p, "done": False} for p in sorted(plants or [], key=lambda p: p.minute)]
        self.rng = np.random.default_rng(match.seed if seed is None else seed)
        # Technique labels draw from their own stream, so adding or changing a label rule never
        # changes the run of play of a seed.
        self.style_rng = np.random.default_rng([(match.seed if seed is None else seed) or 0, 2])
        # Where players stand at corners and free kicks (Ax44): its own stream too.
        self.set_pieces = SetPieceShape(np.random.default_rng([(match.seed if seed is None else seed) or 0, 3]))
        self.touch: dict | None = None            # last reception: who, when, what kind of ball
        self.p = params
        self.teams = [match.home, match.away]
        self.sheets = [match.home.sheet, match.away.sheet]
        self.tactics = [match.home.tactics, match.away.tactics]
        self.players = {pl.player_id: pl for team in self.teams for pl in team.squad}
        self.attr = {pid: self._flatten(pl) for pid, pl in self.players.items()}
        self.shapes = [self._shape(k) for k in (0, 1)]
        self.move = MovementModel(self.rng)
        self.move.offside_slack = self.p.offside_slack
        self.move.line_lift = self.p.line_lift
        ref = match.context.referee
        self.strict = (ref.strictness / 60) if ref else 1.0
        self.card_rate = (ref.card_tendency / 60) if ref else 1.0
        self.crowd = 0.0 if match.context.competition.neutral_venue else min(match.context.attendance / 50000, 1.0)

        self.fx, self.chem = self._effects() if self.p.context_effects else ({}, {})

        self.pos = np.zeros((2, 11, 2))
        self.prev = np.zeros((2, 11, 2))
        self.speed = np.zeros((2, 11))
        self.fitness = np.ones((2, 11))
        if self.fx:
            for k in (0, 1):
                for i, pid in enumerate(self.shapes[k].player_ids):
                    self.fitness[k, i] = self._fit_at_start(pid)
        self._stamina_key: tuple | None = None
        self._stamina_cache = np.zeros((2, 11))
        self._physique_key: tuple | None = None
        self._physique_cache = (np.zeros((2, 11)), np.zeros((2, 11)))
        self.burst = np.zeros((2, 11))             # seconds of recent sprinting (REAL-014)
        self.recovering = np.zeros((2, 11), dtype=bool)
        self.ball = np.array([PITCH_LENGTH / 2, PITCH_WIDTH / 2])
        self.ball_z = 0.0
        self.owner: tuple[int, int] | None = None
        self.flight: dict | None = None
        self.loose = False
        self.dead = 0
        self.restart: dict | None = None
        self.forced: dict | None = None
        self.possession: int | None = None
        self.pid = 0
        self.poss_passes = 0
        self.last_touch = 0
        self.last_loss_t = [-99, -99]
        self.last_press = np.full((2, 11), -99)
        self.carry_start: tuple[np.ndarray, int] | None = None
        self.last_pass: dict | None = None
        self.yellows: dict[str, int] = {}
        self.subs_used = [0, 0]
        self.pending_subs: list[int] = []
        self.kept: set[str] = set()               # players automatic substitutions leave alone (What-if)
        self.score = [0, 0]
        self.urgency = [0.0, 0.0]                 # game state per side, see _update_state
        self.half_counts = {"goals": 0, "subs": 0, "cards": 0, "injuries": 0, "var": 0}

        self.t = 0
        self.half = 0                             # index into HALVES; len(HALVES) once the match is over
        self.in_period = False
        self.record_frames = True                 # What-if reruns only need the score
        self.period = 1
        self.period_start = 0
        self.added: int | None = None
        self.period_end_at: int | None = None
        self.periods: list[PeriodInfo] = []
        self.halves = list(HALVES)                # extra time adds two more (REAL-012)
        self.decided_by = "normal_time"
        self.shootout: list[int] | None = None    # penalties scored in a shootout, home and away
        self.injured: list[tuple[int, str]] = []  # (side, player) waiting for a substitution (REAL-010)
        self.events: list[dict] = []
        self.frames: dict[str, list] = {k: [] for k in ("t", "period", "poss", "ball", "owner", "ids", "pos", "speed", "fit")}

    # --- setup -----------------------------------------------------------------------

    def reseed(self, seed: int) -> None:
        """Draw everything from here on from a new seed, the same way __init__ seeds a match (B08)."""
        self.rng = np.random.default_rng(seed)
        self.style_rng = np.random.default_rng([seed, 2])
        self.set_pieces.rng = np.random.default_rng([seed, 3])
        self.move.rng = self.rng

    @staticmethod
    def _flatten(pl) -> dict[str, float]:
        a = pl.attributes
        flat = {}
        for g in ("attacking", "skill", "movement", "power", "mentality", "defending", "goalkeeping"):
            for k, v in getattr(a, g).model_dump().items():
                flat[k] = v / 99
        flat["pace"] = 0.25 * flat["acceleration"] + 0.75 * flat["sprint_speed"]   # sets the top speed (REAL-014)
        flat["foot"] = pl.preferred_foot
        return flat

    def _shape(self, k: int) -> TeamShape:
        pace = {pid: a["pace"] for pid, a in self.attr.items()}
        return TeamShape.from_sheet(k, self.sheets[k], self.tactics[k], pace)

    def _a(self, k: int, i: int, name: str) -> float:
        pid = self.shapes[k].player_ids[i]
        return self.attr[pid][name] if pid else 0.5

    def _pid(self, k: int, i: int) -> str | None:
        return self.shapes[k].player_ids[i]

    # --- context effects (B14, CTX-001) ------------------------------------------------

    def _effects(self) -> tuple[dict[str, dict[str, float]], dict[tuple[str, str], float]]:
        """Each player's total per target (their own effects plus their side's), and the extra pass
        chemistry between two players who played together before. Read once, at kick-off."""
        ctx = self.match.context
        side = {pl.player_id: pl.team for pl in self.players.values()}
        pair = {r.relationship_id: (r.person_id, r.other_id) for r in ctx.relationships}
        fx: dict[str, dict[str, float]] = {pid: {} for pid in side}
        chem: dict[tuple[str, str], float] = {}
        for e in ctx.effects:
            if e.target == "chemistry" and e.subject_id in side:
                a, b = pair.get(e.source_ref, (None, None))
                partner = b if a == e.subject_id else a
                if partner:
                    chem[e.subject_id, partner] = chem.get((e.subject_id, partner), 0.0) + e.delta
                continue
            for pid, s in side.items():
                if e.subject_id in (pid, s):
                    fx[pid][e.target] = fx[pid].get(e.target, 0.0) + e.delta
        return {pid: t for pid, t in fx.items() if t}, chem

    def _fx(self, pid: str | None, target: str) -> float:
        """The total effect on one player's target; 0.0 with the effects off."""
        if not self.fx or pid is None:
            return 0.0
        return self.fx.get(pid, {}).get(target, 0.0)

    def _times(self, p: float, pid: str | None, target: str) -> float:
        """A rate scaled by (1 + the player's effect on `target`), CTX-001; `p` itself with none."""
        d = self._fx(pid, target)
        return p * (1 + d) if d else p

    def _fit_at_start(self, pid: str | None) -> float:
        return clip1(1.0 + self._fx(pid, "fitness"), 0.0, 1.0)

    def _kickoff_positions(self, kicking: int) -> None:
        for k in (0, 1):
            anchors = self.shapes[k].anchors.copy()
            anchors[:, 0] = np.minimum(anchors[:, 0] * 0.55, 49.0)
            self.pos[k] = from_view(anchors, k)
        self.prev[:] = self.pos
        self.ball = np.array([PITCH_LENGTH / 2, PITCH_WIDTH / 2])
        striker = self._nearest(kicking, self.ball)
        self.pos[kicking, striker] = self.ball

    # --- helpers ---------------------------------------------------------------------

    def _active(self, k: int) -> np.ndarray:
        return self.shapes[k].active

    def _nearest(self, k: int, point: np.ndarray, outfield: bool = False, exclude: int | None = None) -> int:
        d = norm(self.pos[k] - point)
        d = np.where(self._active(k), d, np.inf)
        if outfield:
            d = np.where([r == "GK" for r in self.shapes[k].roles], np.inf, d)
        if exclude is not None:
            d[exclude] = np.inf
        return int(np.argmin(d))

    def _view(self, p: np.ndarray, k: int) -> np.ndarray:
        return to_view(np.asarray(p, dtype=float), k)

    def _opp_lines(self, k: int) -> tuple[float, float]:
        """Opponents' back line (second-last, keeper included) and midfield line in k's view (CONV-009)."""
        opp = 1 - k
        v = self._view(self.pos[opp], k)
        act = self._active(opp)
        xs = np.sort(v[act, 0])[::-1]
        back = xs[1] if len(xs) > 1 else PITCH_LENGTH
        mids = [v[i, 0] for i, r in enumerate(self.shapes[opp].roles) if act[i] and r in MIDFIELD_ROLES]
        mid = float(np.mean(mids)) if mids else back - 15
        return float(back), mid

    def _pressure(self, k: int, i: int) -> tuple[bool, float, int]:
        """(under_pressure, nearest distance, nearest opponent slot) for the carrier (ATTR-001)."""
        opp = 1 - k
        p = self.pos[k, i]
        d = norm(self.pos[opp] - p)
        d = np.where(self._active(opp), d, np.inf)
        prev_d = norm(self.prev[opp] - p)
        closing = prev_d - d
        under = bool(np.any((d <= CLOSE_RADIUS) | ((d <= PRESS_RADIUS) & (closing >= CLOSING_SPEED))))
        j = int(np.argmin(d))
        return under, float(d[j]), j

    def _emit(self, type_: str, k: int, i: int | None = None, **fields) -> dict:
        seq = len(self.events) + 1
        period_t = self.t - self.period_start
        e = {"match_id": self.match.match_id, "seq": seq, "event_id": f"m{self.t // 60:03d}-s{seq:05d}",
             "t": self.t, "period": self.period, "period_t": period_t, "type": type_, "team": SIDES[k],
             "player_id": self._pid(k, i) if i is not None else None, "possession_id": self.pid or None}
        for key, value in fields.items():
            if isinstance(value, np.ndarray):          # a ball over the line is recorded on the line
                value = (round(float(clip1(value[0], 0.0, PITCH_LENGTH)), 1),
                         round(float(clip1(value[1], 0.0, PITCH_WIDTH)), 1))
            e[key] = value
        self.events.append(e)
        return e

    @staticmethod
    def _link(a: dict, b: dict) -> None:
        a.setdefault("related_event_ids", []).append(b["event_id"])
        b.setdefault("related_event_ids", []).append(a["event_id"])

    def _clip_pitch(self, p: np.ndarray) -> np.ndarray:
        return np.array([np.clip(p[0], 0, PITCH_LENGTH), np.clip(p[1], 0, PITCH_WIDTH)])

    def _success(self, k: int, p: float) -> float:
        if k == 0:
            p *= 1 + (self.p.home_boost - 1) * self.crowd
        return float(clip1(p, 0.02, 0.99))

    # --- possession ------------------------------------------------------------------

    def _gain(self, k: int, i: int) -> None:
        if self.possession != k:
            if self.possession is not None:
                self.last_loss_t[self.possession] = self.t
            self.possession = k
            self.pid += 1
            self.poss_passes = 0
            self.last_pass = None
        self.owner = (k, i)
        self.loose = False
        self.flight = None
        self.ball = self.pos[k, i].copy()
        self.ball_z = 0.0
        self.last_touch = k
        self.carry_start = (self.ball.copy(), self.t)

    def _end_carry(self, outcome: str = "success") -> None:
        if self.owner is None or self.carry_start is None:
            return
        k, i = self.owner
        start, _ = self.carry_start
        if norm(self.ball - start) >= 3.0:                     # EVT-002
            sv, ev = self._view(start, k), self._view(self.ball, k)
            back, mid = self._opp_lines(k)
            e = self._emit("carry", k, i, location=start, end_location=self.ball.copy(), outcome=outcome,
                           threat=round(threat_value(ev) - threat_value(sv), 4) if outcome == "success" else 0.0)
            e["_break"] = any(sv[0] < line <= ev[0] for line in (mid, back))
        self.carry_start = (self.ball.copy(), self.t)

    def _lose_ball(self) -> None:
        self.owner = None

    # --- dead ball and restarts ------------------------------------------------------

    def _out_of_play(self, p: np.ndarray, last_team: int) -> None:
        """Ball crossed a line at p: throw-in, corner or goal kick (CONV-006)."""
        x, y = p
        self.owner, self.flight, self.loose = None, None, False
        opp = 1 - last_team
        if 0 < x < PITCH_LENGTH:
            spot = np.array([np.clip(x, 1, PITCH_LENGTH - 1), 0.0 if y <= 0 else PITCH_WIDTH])
            self._set_restart("throw_in", opp, spot, wait=self.rng.integers(8, 19))
            return
        goal_end_team = 0 if x >= PITCH_LENGTH else 1      # team attacking that goal
        defending = 1 - goal_end_team
        if last_team == defending:
            corner_y = 0.0 if y < PITCH_WIDTH / 2 else PITCH_WIDTH
            self._set_restart("corner", goal_end_team, np.array([PITCH_LENGTH if goal_end_team == 0 else 0.0, corner_y]),
                              wait=self.rng.integers(20, 36))
        else:
            spot = from_view(np.array([5.5, PITCH_WIDTH / 2 + uniform(self.rng, -9, 9)]), defending)
            self._set_restart("goal_kick", defending, spot, wait=self.rng.integers(18, 33))

    def _set_restart(self, kind: str, team: int, spot: np.ndarray, wait: int, period_start: bool = False) -> None:
        self.owner, self.flight, self.loose = None, None, False
        self.ball = self._clip_pitch(spot)
        self.ball_z = 0.0
        self.restart = {"kind": kind, "team": team, "spot": self.ball.copy(), "period_start": period_start,
                        "waited": 0}
        self.restart["taker"] = self._choose_taker(team, kind, self.ball)
        # a side protecting a lead takes its time over its own restarts (REAL-001)
        self.dead = int(wait) + int(self.p.waste_s * max(-self.urgency[team], 0.0))

    def _restart_targets(self, targets: np.ndarray) -> None:
        """During a stoppage the taker walks to the ball; after a goal everyone walks back to their half;
        at a corner or free kick everyone goes to his set-piece spot (Ax44, setpieces.py)."""
        self.set_pieces.apply(targets, tuple(self.shapes), self.pos, self.ball, self.owner, self.restart, self.forced,
                              self.flight)
        r = self.restart
        if r is None:
            return
        if r["kind"] == "kick_off" and not r["period_start"]:
            for k in (0, 1):
                anchors = self.shapes[k].anchors.copy()
                anchors[:, 0] = np.minimum(anchors[:, 0] * 0.55, 49.0)
                targets[k] = from_view(anchors, k)
        targets[r["team"], r["taker"]] = r["spot"]

    def _choose_taker(self, k: int, kind: str, spot: np.ndarray) -> int:
        sheet = self.sheets[k]
        taker_id = None
        if kind == "corner":
            left = self._view(spot, k)[1] > PITCH_WIDTH / 2
            taker_id = sheet.corner_taker_left_id if left else sheet.corner_taker_right_id
        elif kind == "penalty":
            taker_id = sheet.penalty_taker_id
        elif kind == "free_kick" and norm(self._view(spot, k) - GOAL) < 32:
            taker_id = sheet.free_kick_taker_id
        ids = self.shapes[k].player_ids
        keeper = self._keeper(k)
        if kind == "goal_kick" and keeper is not None:
            return keeper
        if taker_id is not None and taker_id in ids:
            return ids.index(taker_id)
        return self._nearest(k, spot, outfield=True)

    def _take_restart(self) -> bool:
        """Take the restart once the taker has reached the ball. Returns False while still waiting."""
        r = self.restart
        k, kind, spot, i = r["team"], r["kind"], r["spot"], r["taker"]
        if not self._active(k)[i]:
            i = r["taker"] = self._choose_taker(k, kind, spot)
        if (norm(self.pos[k, i] - spot) > 1.5 or self._encroaching(k, kind, spot)) and r["waited"] < 60:
            r["waited"] += 1
            return False
        self.restart = None
        self.pos[k, i] = spot
        self._gain(k, i)
        self.forced = {"kind": kind}
        return True

    def _encroaching(self, k: int, kind: str, spot: np.ndarray) -> bool:
        """Laws 13 and 17: the referee waits for the opponents to be 9.15 m from a free kick or corner."""
        if kind not in ("corner", "free_kick"):
            return False
        d = norm(self.pos[1 - k] - spot)
        return bool(((d < KEEP_OFF) & self._active(1 - k)).any())

    # --- on-ball actions -------------------------------------------------------------

    def _on_ball(self) -> None:
        k, i = self.owner
        v = self._view(self.ball, k)
        under, d_opp, j = self._pressure(k, i)
        # How he last got the ball, and whether this is his first decision since (ATTR-015).
        last = self.touch if self.touch and self.touch["who"] == (k, i) else None
        quick = last is not None and last["t"] == self.t - 1
        forced, self.forced = self.forced, None
        if forced:
            kind = forced["kind"]
            if kind == "penalty":
                return self._shoot(k, i, v, under=False, penalty=True)
            if kind == "free_kick" and norm(v - GOAL) < 30 and abs(v[1] - 34) < 14 and self.rng.random() < 0.35:
                return self._shoot(k, i, v, under=False, free_kick=True)
            if kind == "header":
                return self._shoot(k, i, v, under=True, header=True)   # headers are never first time (StatsBomb)
            if kind == "loose_shot":                                    # a rebound or loose ball, struck first time
                return self._shoot(k, i, v, under, first_time=True, incoming=None)
            return self._pass(k, i, v, under=False, restart=kind)

        role = self.shapes[k].roles[i]
        if d_opp < 1.8 and self.rng.random() < self.p.tackle_attempt:
            return self._challenge(k, i, j, v)
        if v[0] < 22 and under and role != "GK" and self.rng.random() < self.p.clear_under_pressure:
            return self._clearance(k, i)                             # no time near his own goal: away it goes
        if v[0] > 70:
            xg = xg_model(v, blockers=self._blockers(k, v), pressed=under, finishing=self._a(k, i, "finishing"))
            tendency = 1.2 if role in FORWARD else (0.5 if role in DEFENDER_ROLES else 0.9)
            tendency *= 1 + self.p.state_shot * self.urgency[k]
            if not under and d_opp > 5 and xg < CLOSE_IN_XG and v[0] < PITCH_LENGTH - 8:
                tendency *= self.p.close_in          # free with the ball: take it closer first (REAL-017)
            if xg >= self.p.shot_min_xg and self.rng.random() < min(0.6, (self.p.shot_base + self.p.shot_xg_weight * xg) * tendency):
                return self._shoot(k, i, v, under, first_time=quick, incoming=last)
        dist = float(norm(v - GOAL))
        if 18 <= dist <= 32 and abs(v[1] - PITCH_WIDTH / 2) < 16 and not _in_box(v) and role != "GK":
            if self.rng.random() < self.p.long_shot_rate * self._a(k, i, "long_shots") * (0.5 if under else 1.0) * (
                    1 + self.p.state_shot * self.urgency[k]):
                return self._shoot(k, i, v, under, first_time=quick, incoming=last)
        rate = self.p.pass_rate[self.tactics[k].tempo] + (self.p.pass_rate_pressed if under else 0.0)
        if role == "GK":
            rate = 0.6
        if self.rng.random() < rate:
            return self._pass(k, i, v, under, incoming=last, quick=quick)
        if d_opp < 3.0 and self.rng.random() < 0.08 * self._a(k, i, "dribbling") + 0.01:
            return self._dribble(k, i, j, v)
        self._carry(k, i, v)

    def _carry(self, k: int, i: int, v: np.ndarray) -> None:
        opp = self._view(self.pos[1 - k], k)
        act = self._active(1 - k)
        target = np.array([PITCH_LENGTH - 8, PITCH_WIDTH / 2]) if v[0] > 75 else v + np.array([10.0, 0.0])
        direction = target - v
        near = opp[act]
        if len(near):
            away = v - near[np.argmin(norm(near - v))]
            direction = direction / (norm(direction) + 1e-9) + 0.6 * away / (norm(away) + 1e-9)
        step = uniform(self.rng, 1.5, 4.5) * (0.6 + 0.5 * self._a(k, i, "dribbling"))
        new_v = v + direction / (norm(direction) + 1e-9) * step
        new_v = np.clip(new_v, [0.5, 0.5], [PITCH_LENGTH - 0.5, PITCH_WIDTH - 0.5])
        self.ball = from_view(new_v, k)
        self.pos[k, i] = self.ball

    def _blockers(self, k: int, v: np.ndarray) -> int:
        """Outfield opponents inside the triangle between the ball and the posts."""
        opp = self._view(self.pos[1 - k], k)
        n = 0
        for idx in np.flatnonzero(self._active(1 - k)):
            if self.shapes[1 - k].roles[idx] == "GK":
                continue
            px, py = opp[idx]
            if px <= v[0] or px >= PITCH_LENGTH:
                continue
            frac = (px - v[0]) / max(PITCH_LENGTH - v[0], 0.1)
            lo = v[1] + frac * (PITCH_WIDTH / 2 - 3.66 - v[1])
            hi = v[1] + frac * (PITCH_WIDTH / 2 + 3.66 - v[1])
            if lo - 0.5 <= py <= hi + 0.5:
                n += 1
        return n

    def _challenge(self, k: int, i: int, j: int, v: np.ndarray) -> None:
        """Defender j tries to take the ball from carrier i: foul, tackle won or lost (EVT-008, EVT-013)."""
        opp = 1 - k
        self._end_carry()
        aggression = self._a(opp, j, "aggression")
        careful = 0.25 if self.yellows.get(self._pid(opp, j), 0) else 1.0
        p_foul = self._times(self.p.foul_rate * (0.6 + 0.8 * aggression) * self.strict * careful,
                             self._pid(opp, j), "aggression")                      # B14
        if self.rng.random() < p_foul:
            return self._foul(opp, j, k, i, v)
        tackle = self._a(opp, j, "standing_tackle") * 0.6 + self._a(opp, j, "defensive_awareness") * 0.4
        keep = self._a(k, i, "dribbling") * 0.5 + self._a(k, i, "strength") * 0.2 + self._a(k, i, "ball_control") * 0.3
        # the fresher player has the edge (REAL-009)
        fresh = self.fitness[opp, j] - self.fitness[k, i]
        p_win = float(np.clip(0.45 + 0.6 * (tackle - keep) + 0.5 * self.p.fatigue_err * fresh, 0.1, 0.8))
        won = self.rng.random() < p_win
        e = self._emit("tackle", opp, j, location=self.pos[opp, j].copy(), outcome="success" if won else "fail",
                       success_prob=round(p_win, 3), counterpress=self.t - self.last_loss_t[opp] <= 5)
        if won and _in_box(v) and self.rng.random() < self.p.var_pen_award:
            # the referee waved play on; VAR sees a foul and gives the penalty (REAL-011)
            rev = self._var_review(k, "penalty", e, "overturned", "foul_confirmed")
            self._foul(opp, j, k, i, v, reviewed=rev)
            return
        if won:
            if self.rng.random() < 0.65:
                self._gain(opp, j)
            else:
                self._lose_ball()
                self.loose = True
                self.ball = self._clip_pitch(self.ball + normal(self.rng, 0, 3, 2))

    def _foul(self, k_def: int, j: int, k_att: int, i: int, v: np.ndarray, force_red: str | None = None,
              reviewed: dict | None = None) -> None:
        spot = self.ball.copy()
        penalty = _in_box(v)
        card = None
        reason = None
        r = self.rng.random()
        card_rate = self._times(self.card_rate, self._pid(k_def, j), "card_risk")    # B14
        if force_red:
            card, reason = "red", force_red
        elif r < self.p.red_rate * card_rate:
            card, reason = "red", "serious_foul_play"
        elif r < (self.p.yellow_rate + (0.25 if penalty else 0.0)) * card_rate:
            pid = self._pid(k_def, j)
            self.yellows[pid] = self.yellows.get(pid, 0) + 1
            card = "second_yellow" if self.yellows[pid] >= 2 else "yellow"
            reason = "reckless_challenge"
        detail = FoulDetail(foul_type="tackle", penalty_awarded=penalty, card=card, card_reason=reason).model_dump()
        foul = self._emit("foul", k_def, j, location=self.pos[k_def, j].copy(), foul=detail)
        if reviewed:
            self._link(reviewed, foul)
        if card:
            ce = self._emit("card", k_def, j, location=self.pos[k_def, j].copy(), foul=detail)
            self._link(foul, ce)
            self.half_counts["cards"] += 1
            if card in ("red", "second_yellow"):
                self.shapes[k_def].player_ids[j] = None
                self._react_to_red(k_def)
        self.owner = None
        if penalty and not reviewed and not force_red and self.rng.random() < self.p.var_pen_overturn:
            # VAR: no foul after all; play restarts with the defending keeper (REAL-011)
            rev = self._var_review(k_att, "penalty", foul, "overturned", "no_foul")
            spot = from_view(np.array([5.5, PITCH_WIDTH / 2]), k_def)
            self._set_restart("goal_kick", k_def, spot, wait=self.rng.integers(20, 40) + rev["var"]["duration_s"])
        elif penalty:
            spot = from_view(np.array([PITCH_LENGTH - 11, PITCH_WIDTH / 2]), k_att)
            self._set_restart("penalty", k_att, spot, wait=self.rng.integers(60, 90))
        else:
            self._set_restart("free_kick", k_att, spot, wait=self.rng.integers(12, 30) + (15 if card else 0))
        p_hurt = self._times(self.p.injury_foul, self._pid(k_att, i), "injury_risk")   # B14
        if self.shapes[k_att].player_ids[i] is not None and self.rng.random() < p_hurt:
            self._injure(k_att, i, "contact")

    def _var_review(self, k: int, of: str, event: dict, decision: str, reason: str) -> dict:
        """A VAR review of `event` (REAL-011, EVT-016); k is the side that asked for or gains from it."""
        detail = VarReview(review_of=of, reviewed_event_id=event["event_id"], decision=decision, reason=reason,
                           duration_s=int(self.rng.integers(40, 150))).model_dump()
        rev = self._emit("var_review", k, None, location=event.get("location"), var=detail)
        self._link(event, rev)
        self.half_counts["var"] += 1
        return rev

    def _injure(self, k: int, i: int, cause: str) -> None:
        """A player is hurt (REAL-010, EVT-017). After a knock he is treated and plays on; anything
        worse means a substitution at the next stoppage, or ten men if no change is left."""
        pid = self._pid(k, i)
        if pid is None or self.shapes[k].roles[i] == "GK" or any(p == pid for _, p in self.injured):
            return
        r, severity = self.rng.random(), "serious"
        for name, share in SEVERITY:
            if r < share:
                severity = name
                break
            r -= share
        lo, hi = DAYS_OUT[severity]
        areas = INJURY_AREAS[cause]
        info = InjuryInfo(area=areas[int(self.style_rng.integers(len(areas)))], severity=severity, cause=cause,
                          can_continue=severity == "knock",
                          expected_days_out=int(self.style_rng.integers(lo, hi))).model_dump()
        self._emit("injury", k, i, location=self.pos[k, i].copy(), injury=info)
        self.half_counts["injuries"] += 1
        if self.dead > 0:
            self.dead += int(self.rng.integers(30, 90))           # treatment on the pitch
        if severity == "knock":
            self.fitness[k, i] = max(self.fitness[k, i] - 0.05, 0.0)
        else:
            self.fitness[k, i] = min(self.fitness[k, i], 0.4)     # he limps on until the ball goes dead
            self.injured.append((k, pid))

    def _dribble(self, k: int, i: int, j: int, v: np.ndarray) -> None:
        opp = 1 - k
        self._end_carry()
        att = self._a(k, i, "dribbling") * 0.6 + self._a(k, i, "agility") * 0.4
        dfn = self._a(opp, j, "standing_tackle") * 0.5 + self._a(opp, j, "defensive_awareness") * 0.5
        base = self._times(0.5 + 0.5 * (att - dfn), self._pid(k, i), "composure")   # B14: always pressed
        p = self._success(k, base)
        won = self.rng.random() < p
        d = self._emit("dribble", k, i, location=self.ball.copy(), outcome="success" if won else "fail",
                       success_prob=round(p, 3))
        duel = self._emit("duel", opp, j, location=self.pos[opp, j].copy(), duel_type="ground",
                          outcome="fail" if won else "success")
        self._link(d, duel)
        if won:
            new_v = v + np.array([4.0, 0.0])
            self.ball = from_view(np.clip(new_v, [0.5, 0.5], [104.5, 67.5]), k)
            self.pos[k, i] = self.ball
            self.carry_start = (self.ball.copy(), self.t)
        else:
            self._gain(opp, j)

    # --- passing ---------------------------------------------------------------------

    def _pass(self, k: int, i: int, v: np.ndarray, under: bool, restart: str | None = None,
              incoming: dict | None = None, quick: bool = False) -> None:
        self._end_carry()
        shape = self.shapes[k]
        mates = self._view(self.pos[k], k)
        opp = self._view(self.pos[1 - k], k)
        opp_act = self._active(1 - k)
        back, mid = self._opp_lines(k)
        cand = [m for m in np.flatnonzero(shape.active) if m != i]
        if restart == "kick_off":
            cand = [m for m in cand if mates[m, 0] < v[0] + 1] or cand
        gains = mates[cand, 0] - v[0]
        dists = norm(mates[cand] - v)
        to_opp = opp[opp_act][None, :, :] - mates[cand][:, None, :]      # (candidates, opponents, 2)
        open_ = norm(to_opp).min(axis=1)
        offside = (mates[cand, 0] > back) & (mates[cand, 0] > max(v[0], PITCH_LENGTH / 2))
        style = self.tactics[k].passing
        long_pen = {"short": 1.4, "mixed": 1.0, "direct": 0.55}[style]
        long_pen *= 1 - self.p.state_direct * max(self.urgency[k], 0.0)     # chasing: go longer sooner
        tgain = np.array([threat_value(mates[m]) for m in cand]) - threat_value(v)
        score = (self.p.pass_forward * gains + 0.14 * np.minimum(open_, 10) - long_pen * (dists / 32) ** 2
                 + self.p.pass_threat * tgain)
        score -= np.array([1.2 if shape.roles[m] == "GK" else 0.0 for m in cand])
        score -= self.p.offside_pen * offside
        if restart == "corner":
            score = np.where([_in_box(mates[m]) for m in cand], score + 4, score - 4)
            # aimed past the keeper's reach, not at the man screening him on the line (Ax44)
            score = np.where(mates[cand, 0] > PITCH_LENGTH - 4.0, score - self.p.corner_line_pen, score)
        if restart == "goal_kick" and style == "direct":
            score += 0.08 * dists
        probs = np.exp((score - score.max()) / 0.55)
        probs /= probs.sum()
        r = cand[int(self.rng.choice(len(cand), p=probs))]
        end_v = mates[r] + normal(self.rng, 0, 0.8, 2)
        through = False
        if (restart is None and shape.roles[r] in RUNNERS and v[0] < back - 5 and back - 6 <= mates[r, 0] <= back + 0.5
                and self.rng.random() < self.p.through_lead):
            # a ball into the space behind the line for a runner who starts onside (REAL-016)
            through = True
            end_v = np.array([min(back + uniform(self.rng, 6, 14), PITCH_LENGTH - 3),
                              clip1(mates[r, 1] + normal(self.rng, 0, 2), 3.0, PITCH_WIDTH - 3)])
        if restart == "throw_in":
            end_v = v + (mates[r] - v) * min(1.0, 18 / max(norm(mates[r] - v), 1e-6))
        dist = float(norm(end_v - v))

        # Success probability from distance, skill, lane interceptions and marking (ATTR-007).
        passing = self._a(k, i, "short_passing") if dist < 25 else self._a(k, i, "long_passing")
        acc = 1 - (1 - math.exp(-dist / 80)) * (1.25 - passing)
        acc *= 1 + self.p.skill_pass * (passing - 0.75)
        acc *= 1 - self.p.fatigue_err * (1 - self.fitness[k, i])          # tired legs, sloppier passes (REAL-009)
        seg = end_v - v
        seg_len2 = float(seg[0] * seg[0] + seg[1] * seg[1]) or 1e-6
        lane = []
        opp_idx = np.flatnonzero(opp_act)
        rel = opp[opp_idx] - v
        us = np.clip((rel[:, 0] * seg[0] + rel[:, 1] * seg[1]) / seg_len2, 0, 1)
        points = v + us[:, None] * seg
        dsegs = norm(points - opp[opp_idx])
        for n in np.flatnonzero((us > 0.05) & (dsegs < 2.5)):
            u, dseg = float(us[n]), float(dsegs[n])
            w = self.p.lane_cut * (1 - dseg / 2.5) * (1.2 if u < 0.9 else 0.8)
            w *= 1 + self.p.skill_def * (self._a(1 - k, int(opp_idx[n]), "interceptions") - 0.7)
            w *= 1 - self.p.fatigue_err * (1 - self.fitness[1 - k, opp_idx[n]])
            lane.append((opp_idx[n], w, points[n].copy()))
            acc *= 1 - w
        marks = norm(opp[opp_idx] - end_v)
        mark_d = float(np.min(marks))
        mark_j = int(opp_idx[np.argmin(marks)])
        if mark_d < 2.0:
            acc *= 1 - 0.18 * (1 - mark_d / 2.0)
        if under:
            acc *= 0.88 + 0.1 * self._a(k, i, "composure")
        if self.fx:                                                   # B14, CTX-001
            pid = self._pid(k, i)
            if under:
                acc = self._times(acc, pid, "composure")
            acc = 1 - (1 - acc) * (1 - self._fx(pid, "concentration"))
            acc *= 1 + self._fx(pid, "chemistry") + self.chem.get((pid, shape.player_ids[r]), 0.0)
        if restart in ("throw_in", "kick_off", "free_kick") and dist < 25:
            acc = max(acc, 0.9)
        acc = self._success(k, acc)

        ptype = self._pass_type(k, v, end_v, r, restart, back)
        height = self._pass_height(ptype, dist)
        if height != "ground" and restart is None:          # a ball in the air is harder to bring down
            acc = float(clip1(acc * (self.p.high_pass_acc if height == "high" else (1 + self.p.high_pass_acc) / 2),
                              0.02, 0.99))
        foot = self.attr[self._pid(k, i)]["foot"]
        body = "other" if restart == "throw_in" else (
            f"{foot}_foot" if self.rng.random() < 0.8 else ("right_foot" if foot == "left" else "left_foot"))
        delivery = None
        if ptype in ("cross", "corner"):
            from_left = v[1] > PITCH_WIDTH / 2
            delivery = "inswing" if (from_left and foot == "right") or (not from_left and foot == "left") else "outswing"
        speed_ms = 11 + 0.35 * dist + normal(self.rng, 0, 1.5)
        first_time = quick and restart is None and self.style_rng.random() < FIRST_TIME_PASS_SHARE
        technique, label_height, label_body = self._pass_technique(k, i, v, end_v, dist, height, body, bool(lane),
                                                                   incoming if first_time else None, restart)
        base = dict(location=self.ball.copy(), pass_type=ptype, pass_height=label_height, body_part=label_body,
                    pass_technique=technique, first_time=first_time,
                    delivery=delivery, ball_speed_kmh=round(float(np.clip(speed_ms * 3.6, 20, 140)), 1),
                    under_pressure=under, success_prob=round(acc, 3))
        self.poss_passes += 1

        # Offside (EVT-015).
        if offside[cand.index(r)] and restart not in ("corner", "throw_in", "goal_kick") and self.rng.random() < 0.8:
            pe = self._emit("pass", k, i, end_location=from_view(end_v, k), outcome="fail", receiver_id=None, **base)
            oe = self._emit("offside", k, r, location=from_view(mates[r], k))
            self._link(pe, oe)
            self.owner = None
            self._set_restart("free_kick", 1 - k, from_view(mates[r], k), wait=self.rng.integers(10, 20))
            return

        ok = self.rng.random() < acc
        end_abs = from_view(np.clip(end_v, [0.3, 0.3], [104.7, 67.7]), k)
        if ok and ptype in ("through_ball", "long_ball") and self._keeper_sweep(k, i, end_abs, base, dist / speed_ms):
            return
        if ok:
            pe = self._emit("pass", k, i, end_location=end_abs, outcome="success", receiver_id=self._pid(k, r),
                            threat=round(threat_value(end_v) - threat_value(v), 4), **base)
            pe["_break"] = any(v[0] < line <= end_v[0] for line in (mid, back))
            self.last_pass = {"event": pe, "receiver": (k, r)}
            self.flight = {"team": k, "slot": r, "end": end_abs, "arrive": self.t + max(1, math.ceil(dist / speed_ms)),
                           "cross": ptype in ("cross", "corner") and height == "high", "height": height,
                           "through": through, "pass": pe}
            self.owner = None
            self.ball_z = 2.0 if height == "high" else 0.0
            return

        # Failed pass: interception, contested reception, or inaccurate.
        weights = [w for _, w, _ in lane] + [0.25 * max(0.0, 1 - mark_d / 2.0), 0.15 + (1 - passing) * 0.3]
        weights = np.array(weights) / np.sum(weights)
        cause = int(self.rng.choice(len(weights), p=weights))
        if cause < len(lane):
            j, _, point = lane[cause]
            at = self._clip_pitch(from_view(point, k))              # a pass along the touchline is cut out on it
            pe = self._emit("pass", k, i, end_location=at, outcome="fail", receiver_id=None, **base)
            # a clean interception, or a block or deflection he then collects (EVT-009, EVT-012)
            ie = self._emit("interception" if self.rng.random() < self.p.intercept_share else "ball_recovery",
                            1 - k, j, location=at, counterpress=self.t - self.last_loss_t[1 - k] <= 5)
            self._link(pe, ie)
            self.pos[1 - k, j] = at
            self._gain(1 - k, j)
            return
        if cause == len(lane):
            pe = self._emit("pass", k, i, end_location=end_abs, outcome="fail", receiver_id=None, **base)
            aerial = height == "high"                                   # what happens next follows the real ball
            duel_type = "aerial" if aerial or base["pass_height"] == "high" else "ground"   # a chip is met in the air
            de = self._emit("duel", 1 - k, mark_j, location=end_abs, duel_type=duel_type, outcome="success")
            da = self._emit("duel", k, r, location=end_abs, duel_type=duel_type, outcome="fail")
            self._link(de, da)
            self._link(pe, de)
            self.owner = None
            self.ball = end_abs.copy()
            self.pos[1 - k, mark_j] = end_abs
            if aerial and _in_own_box(self._view(end_abs, 1 - k)):
                return self._clearance(1 - k, mark_j)
            self._gain(1 - k, mark_j)
            return
        miss_v = end_v + normal(self.rng, 0, 3 + 0.15 * dist, 2)
        if ptype in ("cross", "corner") and self.rng.random() < 0.5:
            miss_v = np.array([PITCH_LENGTH + 1, miss_v[1]])          # deflected behind: corner
            pe = self._emit("pass", k, i, end_location=self._clip_pitch(from_view(miss_v, k)), outcome="fail",
                            receiver_id=None, deflected=True, **base)
            return self._out_of_play(from_view(miss_v, k), 1 - k)
        if self.rng.random() < 0.3:                                    # runs out of play
            if abs(miss_v[1] - PITCH_WIDTH / 2) > 18 or miss_v[0] < 85:
                miss_v[1] = -1.0 if miss_v[1] < PITCH_WIDTH / 2 else PITCH_WIDTH + 1
            else:
                miss_v[0] = PITCH_LENGTH + 1
        miss_abs = from_view(miss_v, k)
        pe = self._emit("pass", k, i, end_location=self._clip_pitch(miss_abs), outcome="fail", receiver_id=None, **base)
        if not (0 <= miss_abs[0] <= PITCH_LENGTH and 0 <= miss_abs[1] <= PITCH_WIDTH):
            return self._out_of_play(miss_abs, k)
        self.owner = None
        self.flight = {"team": None, "slot": None, "end": miss_abs, "arrive": self.t + max(1, math.ceil(dist / speed_ms)),
                       "cross": False}

    def _pass_technique(self, k: int, i: int, v: np.ndarray, end_v: np.ndarray, dist: float, height: str,
                        body: str, lane_blocked: bool, incoming: dict | None,
                        restart: str | None) -> tuple[str, str, str]:
        """ATTR-017, first match wins: (technique, pass height, body part) as recorded.
        `incoming` is set only for a first-time pass.

        Target mix over open play, close to what Opta-style data shows: about 90 % normal,
        4 % chipped, 2 % lay-offs, 1 % flick-ons, 1 % outside of the foot, 0.5 % backheels.
        Labels only: the pass itself (target, success) is already decided."""
        if restart is not None or body == "other":
            return "normal", height, body
        r = self.style_rng.random()
        role = self.shapes[k].roles[i]
        forward = end_v[0] - v[0]
        foot = self.attr[self._pid(k, i)]["foot"]
        if incoming and incoming["height"] == "high" and r < 0.55:      # met in the air and headed on
            return ("flick_on" if forward > 0 else "normal"), height, "head"
        if incoming and role in FORWARD and forward < -2 and dist < 15 and r < 0.6:
            return "lay_off", height, body                                # back to goal, set back first time
        if role in FORWARD + tuple(MIDFIELD_ROLES) and forward < 0 and dist < 10 and r < 0.1:
            return "backheel", "ground", body
        if lane_blocked and 10 <= dist <= 35 and r < 0.08:
            return "chip", "high", body                                   # lifted over the man in the lane
        sideways = end_v[1] - v[1]                                        # team view: + is to his left
        if 10 <= dist <= 30 and ((foot == "right" and sideways < -5) or (foot == "left" and sideways > 5)) and r < 0.08:
            return "outside_foot", height, f"{foot}_foot"
        return "normal", height, body

    def _pass_height(self, ptype: str, dist: float) -> str:
        """ATTR-005 (B12): how high the ball travels, by pass type and length. Over a match this
        gives about StatsBomb's 2022 World Cup mix: 75 % on the ground, 8 % low, 17 % high."""
        if ptype == "throw_in":
            return "low"
        if ptype in ("cross", "corner"):
            hi, lo = 0.85, 0.1
        elif ptype in ("long_ball", "switch") or dist >= 32:
            hi, lo = 0.75, 0.15
        elif ptype in ("free_kick", "goal_kick") and dist >= 25:
            hi, lo = 0.7, 0.15
        elif dist >= 20:
            hi, lo = 0.12, 0.2
        else:
            hi, lo = 0.02, 0.03
        r = self.rng.random()
        return "high" if r < hi else ("low" if r < hi + lo else "ground")

    def _keeper(self, k: int) -> int | None:
        """Slot of k's keeper, if he is on the pitch."""
        roles = self.shapes[k].roles
        if "GK" not in roles:
            return None
        g = roles.index("GK")
        return g if self._active(k)[g] else None

    def _keeper_claim(self, k: int) -> bool:
        """A cross dropping into the keeper's area (B12, EVT-005): he comes for it and catches or
        punches it. k is the crossing side."""
        opp = 1 - k
        g = self._keeper(opp)
        if g is None:
            return False
        dv = self._view(self.ball, opp)
        if dv[0] > 13 or abs(dv[1] - PITCH_WIDTH / 2) > 12:
            return False
        if norm(self.pos[opp, g] - self.ball) > CLAIM_REACH:
            return False                                  # he came for it but is not there (no jumps)
        skill = self._a(opp, g, "handling") * 0.5 + self._a(opp, g, "positioning") * 0.5
        if self.rng.random() >= self.p.claim_rate * (1.15 - dv[0] / 13) * (0.5 + 0.6 * skill):
            return False
        punch = self.rng.random() < 0.3
        self.pos[opp, g] = self.ball
        self._emit("goalkeeper", opp, g, location=self.ball.copy(), keeper_action="punch" if punch else "claim",
                   keeper_technique="standing")
        self.last_pass = None
        if punch:
            self.owner, self.loose = None, True
            self.ball = self._clip_pitch(from_view(np.array([uniform(self.rng, 18, 32), uniform(self.rng, 14, 54)]), opp))
        else:
            self._gain(opp, g)
        return True

    def _keeper_sweep(self, k: int, i: int, end_abs: np.ndarray, base: dict, flight_s: float) -> bool:
        """A ball played in behind (B12, EVT-005): the keeper rushes off his line for a ball that
        drops within his reach, runs onto it, and picks it up in his box or clears it."""
        opp = 1 - k
        g = self._keeper(opp)
        if g is None:
            return False
        dv = self._view(end_abs, opp)
        if dv[0] > 30 or abs(dv[1] - PITCH_WIDTH / 2) > 22:
            return False
        d_gk = float(norm(self.pos[opp, g] - end_abs))
        if d_gk > 20 or self.rng.random() >= self.p.sweep_rate * (1 - d_gk / 22):
            return False
        pe = self._emit("pass", k, i, end_location=end_abs, outcome="fail", receiver_id=None, **base)
        ge = self._emit("goalkeeper", opp, g, location=end_abs.copy(), keeper_action="sweep", keeper_technique="standing")
        self._link(pe, ge)
        self.owner, self.last_pass = None, None
        self.flight = {"team": opp, "slot": g, "end": end_abs, "arrive": self.t + max(1, math.ceil(flight_s)),
                       "cross": False, "height": "ground", "sweep": True}
        return True

    def _pass_type(self, k: int, v: np.ndarray, end_v: np.ndarray, r: int, restart: str | None, back: float) -> str:
        """ATTR-004, first match wins."""
        if restart in ("corner", "free_kick", "throw_in", "goal_kick", "kick_off"):
            return restart
        d = float(norm(end_v - v))
        if v[0] >= 70 and (v[1] < 24.84 or v[1] > 43.16) and _in_box(end_v):
            return "cross"
        if v[0] >= PITCH_LENGTH - 6 and end_v[0] < v[0] and _in_box(end_v):
            return "cutback"
        if end_v[0] > back and v[0] < back:
            return "through_ball"
        if abs(end_v[1] - v[1]) > PITCH_WIDTH / 2:
            return "switch"
        if d >= 32:
            return "long_ball"
        if self.shapes[k].roles[r] == "GK":
            return "back_pass"
        return "regular"

    def _arrive(self) -> None:
        f, self.flight = self.flight, None
        self.ball = self._clip_pitch(f["end"])
        self.ball_z = 0.0
        if f["team"] is None:
            self.loose = True
            return
        k, r = f["team"], f["slot"]
        if not self._active(k)[r]:
            self.loose = True
            return
        first = "late" not in f
        if f.get("through") and self._defender_first(f, k, r):
            return
        if first and f["cross"] and self._keeper_claim(k):
            return
        if first and f.get("height") == "high" and not f["cross"] and self._aerial_contest(k, r):
            return
        if norm(self.pos[k, r] - self.ball) > RECEIVE_REACH:
            # he is not there yet: the ball waits where it dropped and he runs onto it, rather
            # than being put there (B11: nobody moves faster than he can run)
            if f.get("late", 0) < LATE_S:
                f["late"] = f.get("late", 0) + 1
                f["arrive"] = self.t + 1
                self.flight = f
                return
            self.loose = True
            return
        self.ball = self.pos[k, r].copy()                     # he collects it where he is
        self._gain(k, r)
        self.touch = {"who": (k, r), "t": self.t, "height": f.get("height", "ground")}
        if f.get("sweep") and not _in_own_box(self._view(self.ball, k)):
            return self._clearance(k, r)                      # a keeper outside his box kicks it away
        if f["cross"]:
            v = self._view(self.ball, k)
            j = self._nearest(1 - k, self.ball, outfield=True)
            att = self._a(k, r, "heading_accuracy") * 0.5 + self._a(k, r, "jumping") * 0.5
            dfn = self._a(1 - k, j, "heading_accuracy") * 0.4 + self._a(1 - k, j, "jumping") * 0.3 + \
                self._a(1 - k, j, "defensive_awareness") * 0.3
            near = norm(self.pos[1 - k, j] - self.ball) <= self.p.aerial_contest
            if near and self.rng.random() < 0.45 + 0.5 * (dfn - att):
                da = self._emit("duel", k, r, location=self.ball.copy(), duel_type="aerial", outcome="fail")
                dd = self._emit("duel", 1 - k, j, location=self.ball.copy(), duel_type="aerial", outcome="success")
                self._link(da, dd)
                self.pos[1 - k, j] = self.ball
                self._gain(1 - k, j)
                return self._clearance(1 - k, j)
            if _in_box(v) and self.rng.random() < 0.7:
                self.forced = {"kind": "header"}

    def _aerial_contest(self, k: int, r: int) -> bool:
        """A long ball dropping near a defender (B12, EVT-007): he challenges in the air. If he wins
        it he heads it clear in his own half and to a team-mate further up. k, r: the intended receiver."""
        opp = 1 - k
        j = self._nearest(opp, self.ball, outfield=True)
        if norm(self.pos[opp, j] - self.ball) > self.p.aerial_contest:
            return False
        att = self._a(k, r, "heading_accuracy") * 0.4 + self._a(k, r, "jumping") * 0.3 + self._a(k, r, "strength") * 0.3
        dfn = self._a(opp, j, "heading_accuracy") * 0.4 + self._a(opp, j, "jumping") * 0.3 + self._a(opp, j, "strength") * 0.3
        won = self.rng.random() < 0.55 + 0.6 * (dfn - att)
        a = self._emit("duel", k, r, location=self.ball.copy(), duel_type="aerial", outcome="fail" if won else "success")
        d = self._emit("duel", opp, j, location=self.ball.copy(), duel_type="aerial", outcome="success" if won else "fail")
        self._link(a, d)
        if not won:
            return False                                      # the receiver wins it and plays on
        self.ball_z = 2.0
        self.pos[opp, j] = self.ball
        self._gain(opp, j)
        if self._view(self.ball, opp)[0] < PITCH_LENGTH / 2:
            self._clearance(opp, j)
        return True

    def _clearance(self, k: int, j: int) -> None:
        """Defender j heads or kicks the ball away (EVT-010)."""
        self._end_carry()
        target_v = np.array([uniform(self.rng, 35, 65), uniform(self.rng, 5, 63)])
        target = from_view(target_v, k)
        self._emit("clearance", k, j, location=self.ball.copy(), end_location=self._clip_pitch(target),
                   body_part="head" if self.ball_z > 1.0 or self.rng.random() < 0.4 else "right_foot")
        self.owner = None
        r = self.rng.random()
        if r < 0.2:
            out = target.copy()
            out[1] = -1.0 if target[1] < PITCH_WIDTH / 2 else PITCH_WIDTH + 1
            return self._out_of_play(out, k)
        if r < 0.2 + self.p.clear_behind and _in_own_box(self._view(self.ball, k)):
            behind = from_view(np.array([-1.0, self._view(self.ball, k)[1]]), k)
            return self._out_of_play(behind, k)
        self.flight = {"team": None, "slot": None, "end": target, "arrive": self.t + 2, "cross": False}

    # --- shooting --------------------------------------------------------------------

    def _shot_technique(self, header: bool, first_time: bool, incoming: dict | None) -> str:
        """ATTR-014 drawn from the real mix for how the ball came to him (SHOT_TECHNIQUE_MIX)."""
        r = self.style_rng.random()
        if header:
            return "diving_header" if r < DIVING_HEADER_SHARE else "normal"
        came = incoming["height"] if incoming else "loose"
        for technique, share in SHOT_TECHNIQUE_MIX[(came, first_time)]:
            if r < share:
                return technique
            r -= share
        return "normal"

    def _shoot(self, k: int, i: int, v: np.ndarray, under: bool, header: bool = False, penalty: bool = False,
               free_kick: bool = False, first_time: bool = False, incoming: dict | None = None) -> None:
        self._end_carry()
        opp = 1 - k
        blockers = 0 if penalty else self._blockers(k, v)
        gk_slot = self.shapes[opp].roles.index("GK") if "GK" in self.shapes[opp].roles else 0
        gk = self.pos[opp, gk_slot].copy()
        technique = "normal"
        if penalty:
            xg = float(np.clip(0.76 + 0.12 * (self._a(k, i, "penalties") - 0.7), 0.6, 0.9))
        else:
            xg = xg_model(v, header=header, blockers=blockers, pressed=under, finishing=self._a(k, i, "finishing"))
            if free_kick:
                xg = min(xg, 0.07) * (0.7 + 0.6 * self._a(k, i, "free_kick_accuracy"))
            else:
                technique = self._shot_technique(header, first_time, incoming)
                xg = float(np.clip(xg * TECHNIQUE_XG[technique], 0.005, 0.95))
        foot = self.attr[self._pid(k, i)]["foot"]
        aim_y = PITCH_WIDTH / 2 + uniform(self.rng, -3.4, 3.4)
        # xG is the chance itself; whether it goes in also depends on the keeper (B12)
        keeper = np.mean([self._a(opp, gk_slot, a) for a in ("diving", "reflexes", "positioning")])
        p_goal = float(clip1(xg * (1 - self.p.skill_gk * (keeper - 0.88)), 0.002, 0.97))
        if under and self.fx:                                   # B14: composure when pressed, not the xG itself
            p_goal = float(clip1(self._times(p_goal, self._pid(k, i), "composure"), 0.002, 0.97))
        r = self.rng.random()
        if r < p_goal:
            outcome = "goal"
        else:
            p_block = 0.0 if penalty else min(0.55, self.p.block_base + self.p.block_per_defender * blockers)
            r2 = self.rng.random()
            if r2 < p_block:
                outcome = "blocked"
            elif r2 < p_block + (1 - p_block) * self.p.saved_share * (0.8 + 0.4 * self._a(k, i, "finishing")):
                outcome = "saved"
            elif r2 < p_block + (1 - p_block) * (self.p.saved_share + self.p.post_share):
                outcome = "post"
            else:
                outcome = "off_target"
                aim_y += self.rng.choice([-1, 1]) * uniform(self.rng, 4, 9)
        ruled_out = None
        if outcome == "goal" and not penalty and self.rng.random() < self.p.var_disallow:
            # VAR rules it out (REAL-011, EVT-016): mostly offside in the build-up
            outcome = "disallowed"
            ruled_out = ("offside", "offside", "offside", "foul_in_build_up", "handball")[int(self.style_rng.integers(5))]
        end_v = np.array([PITCH_LENGTH, aim_y])
        power = self._a(k, i, "shot_power")
        shot = self._emit(
            "shot", k, i, location=self.ball.copy(), end_location=from_view(end_v, k), shot_outcome=outcome,
            xg=round(xg, 4), body_part="head" if header else f"{foot}_foot", under_pressure=under,
            shot_technique=technique, first_time=first_time, keeper_location=gk,
            shot_end_height_m=round(float(uniform(self.rng, 0.1, 2.3) if outcome in ("goal", "saved", "disallowed")
                                          else uniform(self.rng, 0, 4)), 2),
            ball_speed_kmh=round(float(np.clip((55 if header else 75) + 40 * power + normal(self.rng, 0, 8), 30, 135)), 1),
            play_pattern_hint="penalty" if penalty else ("free_kick" if free_kick else None),
        )
        if self.last_pass and self.last_pass["receiver"] == (k, i) and self.last_pass["event"]["possession_id"] == self.pid:
            self._link(self.last_pass["event"], shot)
        self.last_pass = None
        self.owner = None
        if ruled_out:
            rev = self._var_review(k, "goal", shot, "overturned", ruled_out)
            self.possession = None
            return self._set_restart("free_kick", opp, self._clip_pitch(self.ball),
                                     wait=int(self.rng.integers(30, 60)) + rev["var"]["duration_s"])
        if outcome == "goal":
            self._emit("goalkeeper", opp, gk_slot, location=gk, keeper_action="goal_conceded",
                       keeper_technique="diving" if self.rng.random() < 0.6 else "standing")
            self.score[k] += 1
            self.half_counts["goals"] += 1
            self.possession = None
            wait = int(self.rng.integers(45, 70))
            if self.rng.random() < self.p.var_check:             # checked by VAR, and it stands (REAL-011)
                reason = ("offside", "foul_in_build_up", "handball")[int(self.style_rng.integers(3))]
                wait += self._var_review(k, "goal", shot, "confirmed", reason)["var"]["duration_s"]
            return self._set_restart("kick_off", opp, np.array([PITCH_LENGTH / 2, PITCH_WIDTH / 2]), wait=wait)
        if outcome == "saved":
            action = self.rng.choice(["shot_saved", "shot_parried", "tipped_over"], p=[0.5, 0.35, 0.15])
            ge = self._emit("goalkeeper", opp, gk_slot, location=gk, keeper_action=str(action),
                            keeper_technique="diving" if self.rng.random() < 0.55 else "standing")
            self._link(shot, ge)
            if action == "shot_saved":
                self.pos[opp, gk_slot] = gk
                return self._gain(opp, gk_slot)
            if action == "tipped_over":
                return self._out_of_play(from_view(np.array([PITCH_LENGTH + 1, aim_y]), k), opp)
            self.loose = True
            self.ball = from_view(np.array([PITCH_LENGTH - uniform(self.rng, 4, 10), aim_y + normal(self.rng, 0, 6)]), k)
            return
        if outcome == "blocked":
            j = self._nearest(opp, self.ball, outfield=True)
            be = self._emit("block", opp, j, location=self.pos[opp, j].copy())
            self._link(shot, be)
            if self.rng.random() < 0.45:
                return self._out_of_play(from_view(np.array([PITCH_LENGTH + 1, v[1]]), k), opp)
            self.loose = True
            self.ball = self._clip_pitch(self.pos[opp, j] + normal(self.rng, 0, 4, 2))
            return
        if outcome == "post":
            self.loose = True
            self.ball = from_view(np.array([PITCH_LENGTH - uniform(self.rng, 2, 9), aim_y + normal(self.rng, 0, 5)]), k)
            return
        self._out_of_play(from_view(np.array([PITCH_LENGTH + 1, aim_y]), k), k)

    # --- loose balls -----------------------------------------------------------------

    def _loose_ball(self) -> None:
        d = [np.where(self._active(k), norm(self.pos[k] - self.ball), np.inf) for k in (0, 1)]
        j = [int(np.argmin(d[k])) for k in (0, 1)]
        near = [d[k][j[k]] for k in (0, 1)]
        if min(near) > 1.5:
            return
        if max(near) < 1.2 and self.rng.random() < 0.5:
            w0 = self._a(0, j[0], "strength") + self._a(0, j[0], "reactions")
            w1 = self._a(1, j[1], "strength") + self._a(1, j[1], "reactions")
            win = 0 if self.rng.random() < w0 / (w0 + w1) else 1
            a = self._emit("duel", win, j[win], location=self.ball.copy(), duel_type="ground", outcome="success")
            b = self._emit("duel", 1 - win, j[1 - win], location=self.ball.copy(), duel_type="ground", outcome="fail")
            self._link(a, b)
        else:
            win = int(np.argmin(near))
        if self.possession != win:
            self._emit("ball_recovery", win, j[win], location=self.ball.copy())
        self.pos[win, j[win]] = self.ball
        self._gain(win, j[win])
        self.touch = {"who": (win, j[win]), "t": self.t, "height": "loose"}
        v = self._view(self.ball, win)
        if _in_own_box(v) and self._pressure(win, j[win])[1] < 4.0:
            self._clearance(win, j[win])
        elif v[0] > 80 and self.shapes[win].roles[j[win]] != "GK":
            # a rebound or a loose ball in front of goal is struck first time (B12)
            xg = xg_model(v, blockers=self._blockers(win, v), pressed=True, finishing=self._a(win, j[win], "finishing"))
            if xg >= self.p.shot_min_xg and self.rng.random() < min(0.9, self.p.loose_shot * (1 + 8 * xg)):
                self.forced = {"kind": "loose_shot"}

    # --- pressure events -------------------------------------------------------------

    def _pressures(self) -> None:
        if self.owner is None:
            return
        k, i = self.owner
        opp = 1 - k
        p = self.pos[k, i]
        radius = PRESS_RADIUS_GK if self.shapes[k].roles[i] == "GK" else PRESS_RADIUS
        d = norm(self.pos[opp] - p)
        closing = norm(self.prev[opp] - p) - d
        hits = self._active(opp) & (d <= radius) & (closing >= CLOSING_SPEED)
        hits &= np.array([(opp, j) in self.move.pressers for j in range(11)])   # only players closing him down
        for j in np.flatnonzero(hits):
            if self.t - self.last_press[opp, j] >= 4:
                self.last_press[opp, j] = self.t
                self._emit("pressure", opp, int(j), location=self.pos[opp, j].copy(),
                           counterpress=self.t - self.last_loss_t[opp] <= 5)

    # --- clock, substitutions --------------------------------------------------------

    def _maybe_subs(self) -> None:
        minute = self.t // 60
        limit = SUB_LIMIT[self.period >= 3]
        if self.dead > 0 and self.injured:
            for k, pid in list(self.injured):
                self.injured.remove((k, pid))
                if pid not in self.shapes[k].player_ids:
                    continue                                  # already off
                if self.subs_used[k] >= limit or not self._substitute(k, pid, reason="injury"):
                    i = self.shapes[k].player_ids.index(pid)  # no change left: ten men (EVT-017)
                    self.shapes[k].player_ids[i] = None
                    self._react_to_red(k)
        for k in (0, 1):
            due = sum(minute >= m for m in (58, 68, 78, 85, 100))
            if self.subs_used[k] < min(due, limit) and k not in self.pending_subs:
                self.pending_subs.append(k)
        if self.dead <= 0 or not self.pending_subs:
            return
        for k in list(self.pending_subs):
            self.pending_subs.remove(k)
            self._substitute(k)

    def _substitute(self, k: int, off_id: str | None = None, on_id: str | None = None,
                    reason: str = "fatigue") -> bool:
        shape, sheet = self.shapes[k], self.sheets[k]
        # players named in a planted substitution still to come are kept for it
        reserved = set() if off_id is not None else {
            str(pl["spec"].params[key]) for pl in self.plants if not pl["done"]
            for key in ("player_off", "player_on") if key in pl["spec"].params} | self.kept
        outfield = [i for i, pid in enumerate(shape.player_ids) if pid and shape.roles[i] != "GK" and pid not in reserved]
        if not outfield or not sheet.bench:
            return False
        if off_id is not None and off_id in shape.player_ids:
            i = shape.player_ids.index(off_id)
        else:
            i = min(outfield, key=lambda s: self.fitness[k, s])
            if self.fitness[k, i] > 0.85:
                return False
        off = shape.player_ids[i]
        bench = [b for b in sheet.bench if self.players[b].role != "GK" and b not in reserved]
        if not bench:
            return False
        same = [b for b in bench if self.players[b].position == self.players[off].position]
        on = on_id if on_id in sheet.bench else (same or bench)[0]
        starters = [LineupSlot(player_id=on if s.player_id == off else s.player_id, slot=s.slot, role=s.role,
                               anchor=s.anchor) for s in sheet.starters]
        new_sheet = sheet.model_copy(update={"starters": starters, "bench": [b for b in sheet.bench if b != on]})
        self.sheets[k] = new_sheet
        pace = {pid: a["pace"] for pid, a in self.attr.items()}
        removed = [idx for idx, pid in enumerate(shape.player_ids) if pid is None]
        self.shapes[k] = TeamShape.from_sheet(k, new_sheet, self.tactics[k], pace)
        for idx in removed:
            self.shapes[k].player_ids[idx] = None
        self.fitness[k, i] = self._fit_at_start(self._pid(k, i)) if self.fx else 1.0
        self.burst[k, i], self.recovering[k, i] = 0.0, False
        self.subs_used[k] += 1
        self.half_counts["subs"] += 1
        self._emit("substitution", k, i, substitution=Substitution(player_off_id=off, player_on_id=on,
                                                                    slot=i + 1, reason=reason).model_dump(),
                   team_sheet=new_sheet.model_dump(mode="json"))
        return True

    def _change_tactics(self, k: int, changes: dict) -> None:
        """Coach decision: new tactics and, optionally, a new formation (emits tactical_shift)."""
        tactic_keys = {"line_height", "press", "width", "tempo", "passing", "attack_focus"}
        update = {key: changes[key] for key in tactic_keys if key in changes}
        self.tactics[k] = self.tactics[k].model_copy(update=update)
        sheet = self.sheets[k]
        formation = changes.get("formation")
        if formation and formation in FORMATIONS:
            sheet = self._reshape(k, formation)
        self.sheets[k] = sheet
        old_ids = list(self.shapes[k].player_ids)
        removed = {s.player_id for s in sheet.starters if s.player_id not in old_ids}
        pace = {pid: a["pace"] for pid, a in self.attr.items()}
        self.shapes[k] = TeamShape.from_sheet(k, sheet, self.tactics[k], pace)
        self.shapes[k].player_ids = [None if pid in removed else pid for pid in self.shapes[k].player_ids]
        self._follow_slots(k, old_ids)
        self._emit("tactical_shift", k, None, team_sheet=sheet.model_dump(mode="json"),
                   tactics=self.tactics[k].model_dump(mode="json"))

    def _follow_slots(self, k: int, old_ids: list[str | None]) -> None:
        """After a reshape a player may sit in a new slot: carry his position, fitness and the
        rest of his per-slot state with him."""
        new_ids = self.shapes[k].player_ids
        src = [old_ids.index(pid) if pid is not None and pid in old_ids else n for n, pid in enumerate(new_ids)]
        if src == list(range(11)):
            return
        for arr in (self.pos, self.prev, self.speed, self.fitness, self.last_press, self.burst, self.recovering,
                    self.move.offsets, self.move.offset_until, self.move.run_until):
            arr[k] = arr[k][src]
        if self.owner is not None and self.owner[0] == k:
            self.owner = (k, new_ids.index(old_ids[self.owner[1]]))

    def _react_to_red(self, k: int) -> None:
        """Coach reaction to a sending-off: pull a forward back so the back line stays whole
        (4-4-1 with ten), and press less unless chasing the game. A keeper sent off is replaced in
        goal by the deepest outfield player (#347): the reshape puts him in the keeper's slot."""
        shape = self.shapes[k]
        outfield = sum(1 for p, r in zip(shape.player_ids, shape.roles) if p is not None and r != "GK")
        if self._keeper(k) is None:
            if outfield >= 2:
                self._change_tactics(k, {"formation": self.sheets[k].formation})
            return
        if outfield < 7:
            return
        # With ten the 11-man side takes about two thirds of the shots (scripts/red_card_report.py).
        changes: dict = {"formation": "4-4-2" if outfield == 9 else "4-3-3"}
        if self.score[k] >= self.score[1 - k]:                 # not behind: stop chasing the ball high up
            changes["press"] = {"high": "mid", "mid": "low", "low": "low"}[self.tactics[k].press]
        self._change_tactics(k, changes)

    def _reshape(self, k: int, formation: str) -> TeamSheet:
        """Map the players on the pitch onto a new formation, back to front and left to right."""
        old = sorted(self.sheets[k].starters, key=lambda s: s.slot)
        on_pitch = [s for s in old if s.player_id in self.shapes[k].player_ids]
        gk = [s for s in on_pitch if s.role == "GK"]
        field = sorted((s for s in on_pitch if s.role != "GK"), key=lambda s: (s.anchor[0], -s.anchor[1]))
        if not gk and field:                  # the keeper was sent off: the deepest player goes in goal (#347)
            gk, field = field[:1], field[1:]
        template = FORMATIONS[formation]
        slots = sorted(range(1, len(template)), key=lambda n: (template[n][1], -template[n][2]))[:len(field)]
        starters = [LineupSlot(player_id=s.player_id, slot=1, role="GK", anchor=template[0][1:]) for s in gk]
        for s, n in zip(field, slots):
            role, ax, ay = template[n]
            starters.append(LineupSlot(player_id=s.player_id, slot=n + 1, role=role, anchor=(ax, ay)))
        return self.sheets[k].model_copy(update={"formation": formation, "starters": starters})

    def _plant_due(self, minute: int) -> bool:
        """A plant's minute is the scoreboard minute: 63 fires once the clock shows 63',
        never in the previous half's added time (a 46 waits for the second half)."""
        if self.period == 5:
            return False
        base, length = PERIOD_BASE_MINUTE[self.period], PERIOD_LENGTH_MINUTES[self.period]
        if minute <= base:
            return True
        return minute <= base + length and base * 60 + self.t - self.period_start >= (minute - 1) * 60

    def _apply_plants(self) -> None:
        """Force planted events once their minute has come (B04, PlantSpec)."""
        for n, plant in enumerate(self.plants):
            spec = plant["spec"]
            if plant["done"] or not self._plant_due(spec.minute):
                continue
            first = len(self.events)
            k = 0 if spec.team == "home" else 1
            params = dict(spec.params)
            if spec.type == "red_card":
                # A real foul: the planted player (or the nearest team-mate) brings down the carrier.
                if self.owner is None or self.owner[0] != 1 - k or self.dead > 0:
                    continue
                ids = self.shapes[k].player_ids
                pid = params.get("player_id")
                if pid is not None and pid in ids:
                    j = ids.index(pid)
                else:
                    j = self._nearest(k, self.ball, outfield=True)
                ka, ia = self.owner
                self._end_carry()
                self._foul(k, j, ka, ia, self._view(self.ball, ka),
                           force_red=str(params.get("reason", "professional_foul")))
                plant["done"] = True
            elif spec.type in ("substitution", "press_change", "formation_change"):
                if self.dead <= 0:
                    continue                                  # changes happen at the next stoppage
                if spec.type == "substitution":
                    self._substitute(k, params.get("player_off"), params.get("player_on"),
                                     reason=str(params.get("reason", "tactical")))
                if any(key in params for key in ("line_height", "press", "width", "tempo", "passing", "formation")):
                    self._change_tactics(k, params)
                plant["done"] = True
            for e in self.events[first:]:
                e["_plant"] = n                       # which plant made it, so What-if can find it

    def _clock(self) -> None:
        period_t = self.t - self.period_start
        length = PERIOD_LENGTH_MINUTES[self.period]
        if self.added is None and period_t >= (length - 1) * 60:
            h = self.half_counts
            added = (ADDED_BASE[self.period] + 0.5 * h["goals"] + 0.25 * h["subs"] + 0.3 * h["cards"]
                     + 0.4 * h["injuries"] + 0.6 * h["var"] + normal(self.rng, 0, 0.6))
            self.added = int(np.clip(round(added), *ADDED_RANGE[self.period]))
            self._emit("added_time", self.possession or 0, None, added_minutes=self.added)
            self.period_end_at = length * 60 + self.added * 60 + int(self.rng.integers(0, 40))

    def _period_over(self) -> bool:
        return self.period_end_at is not None and self.t - self.period_start >= self.period_end_at and self.flight is None

    # --- main loop -------------------------------------------------------------------

    def _start_period(self, kicking: int) -> None:
        self.period_start = self.t
        self.added, self.period_end_at = None, None
        self.half_counts = {"goals": 0, "subs": 0, "cards": 0, "injuries": 0, "var": 0}
        self._kickoff_positions(kicking)
        if self.period == 1:
            for k in (0, 1):
                self._emit("kickoff", k, None, location=self.ball.copy(),
                           team_sheet=self.sheets[k].model_dump(mode="json"),
                           tactics=self.tactics[k].model_dump(mode="json"))
        else:
            self._emit("kickoff", kicking, None, location=self.ball.copy())
        self.possession = None
        self._set_restart("kick_off", kicking, self.ball.copy(), wait=1, period_start=True)

    def _tick(self) -> None:
        start = self.pos.copy()                   # where everybody was in the last frame
        if self.dead > 0:
            self.dead -= 1
            if self.dead == 0 and self.restart and not self._take_restart():
                self.dead = 1
        elif self.flight is not None:
            if self.t >= self.flight["arrive"]:
                self._arrive()
        elif self.owner is not None:
            self._on_ball()
        elif self.loose:
            self._loose_ball()
        self._apply_plants()
        self._pressures()
        self._maybe_subs()
        self._update_state()

        carrier = self.owner
        flight_target = None
        if self.flight and self.flight["team"] is not None:
            flight_target = (self.flight["team"], self.flight["slot"], self.flight["end"])
        possession = self.restart["team"] if self.restart else self.possession
        targets = self.move.targets(self.t, tuple(self.shapes), self.pos, self.ball, possession, carrier,
                                    self.loose, tuple(self.last_loss_t), flight_target)
        if carrier is not None:
            targets[carrier] = self.ball
        self._keeper_targets(targets)
        self._restart_targets(targets)
        self.prev = self.pos.copy()
        active = np.stack([self._active(0), self._active(1)])
        self._move(targets, active)
        if carrier is not None:
            self.pos[carrier] = self.ball
        drain = (0.00003 + 0.000022 * self.speed + 0.00004 * (self.speed > 7)) * (1.45 - self._stamina())
        if self.fx:
            drain = drain * self._slot_factor("stamina_decay")     # B14: a late night, legs go sooner
        self.fitness = np.clip(self.fitness - drain, 0, 1)
        for n in np.flatnonzero(self.speed > 7):                   # sprinting: now and then a muscle goes
            k, i = divmod(int(n), 11)
            p_pull = self._times(self.p.injury_sprint * (1.3 - self.fitness[k, i]), self._pid(k, i), "injury_risk")
            if self.rng.random() < p_pull:
                self._injure(k, i, "fatigue" if self.fitness[k, i] < 0.7 else "non_contact")
        self._limit_steps(start)
        self._settle()
        self._record_frame()
        self._clock()

    def _settle(self) -> None:
        """Round the state that carries over to the next second (Bx7): the same seed then plays
        the same match on every machine."""
        self.pos, self.ball = settle(self.pos), settle(self.ball)
        self.speed, self.burst = settle(self.speed), settle(self.burst)
        self.fitness = settle(self.fitness, 9)                # drains by about 1e-5 a second

    def _limit_steps(self, start: np.ndarray) -> None:
        """A pick-up and a run in the same second must not add up to more than his top speed
        (B11, REAL-014): shorten the step, and the ball comes with the man on it."""
        top = self._physique()[0]
        step = self.pos - start
        dist = norm(step)
        over = dist > top
        if not over.any():
            return
        scale = np.where(over, top / np.maximum(dist, 1e-9), 1.0)
        self.pos = start + step * scale[..., None]
        if self.owner is not None and over[self.owner]:
            self.ball = self.pos[self.owner].copy()

    def _update_state(self) -> None:
        """Game state (B12, REAL-001): the score, the clock and the players on the pitch change how
        each side plays. Urgency grows from 30' to 85': a side ahead drops deeper, presses less and
        slows its restarts; a side behind pushes up, presses, shoots sooner and goes longer. A side
        with a player more pushes up; a side a man short drops off."""
        minute = PERIOD_BASE_MINUTE.get(self.period, 90) + (self.t - self.period_start) / 60
        w = clip1((minute - 30) / 55, 0.0, 1.0)
        men = [int(np.count_nonzero(self._active(k))) for k in (0, 1)]
        for k in (0, 1):
            d = self.score[k] - self.score[1 - k]
            u = 0.0 if d == 0 else (URGENCY_LEAD if d > 0 else URGENCY_TRAIL)[min(abs(d), 3) - 1]
            self.urgency[k] = u * w
            extra = max(min(men[k] - men[1 - k], 2), -2)
            self.move.line_shift[k] = self.p.state_line * self.urgency[k] + self.p.man_line * extra
            at = self.p.state_press_at
            self.move.press_shift[k] = 1 if self.urgency[k] > at else -1 if self.urgency[k] < -at else 0

    def _defender_first(self, f: dict, k: int, r: int) -> bool:
        """A ball in behind (REAL-016): the nearest defender gets there first if he is closer
        than the runner; the pass then counts as failed and he has the ball."""
        j = self._nearest(1 - k, self.ball, outfield=True)
        d_def = float(norm(self.pos[1 - k, j] - self.ball))
        if d_def > RECEIVE_REACH or d_def >= float(norm(self.pos[k, r] - self.ball)):
            return False
        pe = f.get("pass")
        if pe is not None:
            pe.update(outcome="fail", receiver_id=None, threat=0.0)
        self.last_pass = None
        self._emit("ball_recovery", 1 - k, j, location=self.ball.copy())
        self.pos[1 - k, j] = self.ball if d_def <= 1.0 else self.pos[1 - k, j]
        self.ball = self.pos[1 - k, j].copy()
        self._gain(1 - k, j)
        return True

    def _keeper_targets(self, targets: np.ndarray) -> None:
        """A cross dropping into his area: the keeper sets off for it while it is in the air
        (REAL-006). A ball played in behind: the nearest defender races the runner for it (REAL-016)."""
        f = self.flight
        if f and f.get("through") and f["team"] is not None:
            opp = 1 - f["team"]
            j = self._nearest(opp, f["end"], outfield=True)
            targets[opp, j] = f["end"]
            self.move.urgent[opp, j] = True
        if not f or not f.get("cross") or f["team"] is None:
            return
        opp = 1 - f["team"]
        g = self._keeper(opp)
        dv = self._view(f["end"], opp)
        if g is not None and dv[0] <= 13 and abs(dv[1] - PITCH_WIDTH / 2) <= 12:
            targets[opp, g] = f["end"]
            self.move.urgent[opp, g] = True

    def _move(self, targets: np.ndarray, active: np.ndarray) -> None:
        """One second of running (REAL-014): own top speed, acceleration, and a jog after a run of sprints."""
        top, accel = self._physique()
        top = np.where(self.recovering, np.minimum(top, RECOVER_MS), top)
        # a defender or holding midfielder far out of position while defending sprints back
        far = norm(targets - self.pos) > URGENT_GAP
        backs = np.array([[r in DEFENDER_ROLES or r == "DM" for r in self.shapes[k].roles] for k in (0, 1)])
        defending = np.array([[self.possession is not None and self.possession != k] * 11 for k in (0, 1)])
        urgent = self.move.urgent | (far & backs & defending)
        if self.owner is not None:
            urgent[self.owner] = True                         # the man on the ball runs with it as he likes
        if self.restart is not None:
            urgent[self.restart["team"], self.restart["taker"]] = True
        self.pos, self.speed = MovementModel.step(self.pos, targets, top, self.fitness, active, self.speed, accel,
                                                  urgent)
        sprinting = self.speed >= SPRINT_MS
        self.burst = np.where(sprinting, self.burst + 1,
                              np.maximum(self.burst - np.where(self.speed < 4, 1.0, 0.4), 0.0))
        self.recovering = (self.recovering | (self.burst >= BURST_S)) & (self.burst > RECOVERED_S)

    def _physique(self) -> tuple[np.ndarray, np.ndarray]:
        """(2, 11) top speed and acceleration of whoever is in each slot, rebuilt when the players change."""
        key = (tuple(self.shapes[0].player_ids), tuple(self.shapes[1].player_ids))
        if key != self._physique_key:
            self._physique_key = key
            pace = np.array([[self._a(k, i, "pace") for i in range(11)] for k in (0, 1)])
            acc = np.array([[self._a(k, i, "acceleration") for i in range(11)] for k in (0, 1)])
            top = top_speed(pace)
            if self.fx:
                top = top * self._slot_factor("motivation")          # B14: run harder, sprint more
            self._physique_cache = (top, ACCEL_MS2[0] + ACCEL_MS2[1] * acc)
        return self._physique_cache

    def _slot_factor(self, target: str) -> np.ndarray:
        """(2, 11) 1 + the effect on `target` of whoever is in each slot (B14)."""
        return np.array([[1.0 + self._fx(self._pid(k, i), target) for i in range(11)] for k in (0, 1)])

    def _stamina(self) -> np.ndarray:
        """(2, 11) stamina of whoever is in each slot, rebuilt only when the players on the pitch change."""
        key = (tuple(self.shapes[0].player_ids), tuple(self.shapes[1].player_ids))
        if key != self._stamina_key:
            self._stamina_key = key
            self._stamina_cache = np.array([[self._a(k, i, "stamina") for i in range(11)] for k in (0, 1)])
        return self._stamina_cache

    def _record_frame(self) -> None:
        if not self.record_frames:
            return
        f = self.frames
        f["t"].append(self.t)
        f["period"].append(self.period)
        dead = self.dead > 0
        f["poss"].append(-1 if dead or self.possession is None else self.possession)
        f["ball"].append((self.ball[0], self.ball[1], self.ball_z))
        f["owner"].append(self._pid(*self.owner) if self.owner else None)
        f["ids"].append([list(self.shapes[0].player_ids), list(self.shapes[1].player_ids)])
        f["pos"].append(self.pos.copy())
        f["speed"].append(self.speed.copy())
        f["fit"].append(self.fitness.copy())

    def play(self, until_t: int | None = None) -> bool:
        """Play on to elapsed second `until_t` (not yet played) or to full time; True once it is over.

        Stopping and playing on gives exactly the match an uninterrupted run gives, so a deepcopy
        of a stopped engine is a save that can be played on many times (B04).
        """
        while self.half < len(self.halves):
            period, kicking = self.halves[self.half]
            if not self.in_period:
                self.period = period
                self._start_period(kicking)
                self.in_period = True
            while not self._period_over():
                if until_t is not None and self.t >= until_t:
                    return False
                self._tick()
                self.t += 1
            self.t -= 1                                   # the whistle goes on the last second played
            self._end_carry()
            self.owner, self.flight, self.loose, self.restart, self.dead = None, None, False, None, 0
            self._emit("period_end", 0, None)
            self.periods.append(PeriodInfo(period=period, start_t=self.period_start, end_t=self.t,
                                           added_minutes=self.added))
            self.t += 1
            self.half += 1
            self.in_period = False
            if self.half == len(self.halves):
                self._after_full_time(period)
        return True

    def _after_full_time(self, period: int) -> None:
        """Knock-out ties (REAL-012): level after 90 minutes, two halves of 15 minutes; still level,
        a penalty shootout. League matches just end."""
        comp = self.match.context.competition
        if self.score[0] != self.score[1]:
            if period > 2:
                self.decided_by = "extra_time"
        elif period == 2 and comp.extra_time:
            self.halves += [(3, 0), (4, 1)]
        elif comp.penalty_shootout:
            self._shootout()

    def _shootout(self) -> None:
        """Penalty shootout (REAL-012, EVT-004): five kicks each, then sudden death, all at one goal.
        Each kick is a shot in period 5 with its round; none counts in the match statistics. The
        players wait in the centre circle and the taker walks to the spot, so the frames go on."""
        self.period, self.period_start = 5, self.t
        self.possession, self.owner = None, None
        order = []
        for k in (0, 1):
            ids = [i for i, pid in enumerate(self.shapes[k].player_ids) if pid is not None]
            keepers = [i for i in ids if self.shapes[k].roles[i] == "GK"]
            order.append(sorted((i for i in ids if i not in keepers), key=lambda i: -self._a(k, i, "penalties")) + keepers)
        circle = np.array([PITCH_LENGTH / 2, PITCH_WIDTH / 2])
        for k in (0, 1):
            ring = np.arange(11) * 0.57 + k * 3.14
            self.pos[k] = settle(circle + np.stack([np.cos(ring), np.sin(ring)], 1) * 8)
        goals, taken = [0, 0], [0, 0]
        first = int(self.rng.integers(2))
        rnd = 0
        while True:
            rnd += 1
            for k in (first, 1 - first):
                i = order[k][(rnd - 1) % len(order[k])]
                goals[k] += self._shootout_kick(k, i, rnd)
                taken[k] += 1
                if taken[0] == taken[1] >= 5 and goals[0] != goals[1]:
                    break
                if max(taken) <= 5 and (goals[0] + 5 - taken[0] < goals[1] or goals[1] + 5 - taken[1] < goals[0]):
                    break
            else:
                continue
            break
        self.shootout, self.decided_by = goals, "penalties"
        self.t -= 1                                           # the last second with a frame
        self._emit("period_end", 0, None)
        self.periods.append(PeriodInfo(period=5, start_t=self.period_start, end_t=self.t))
        self.t += 1

    def _shootout_kick(self, k: int, i: int, rnd: int) -> int:
        """One shootout kick: the taker walks to the spot, the other side's keeper to his line."""
        opp = 1 - k
        g = self._keeper(opp)
        spot = np.array([PITCH_LENGTH - 11, PITCH_WIDTH / 2])
        circle = self.pos.copy()
        targets = circle.copy()
        targets[k, i] = spot
        if g is not None:
            targets[opp, g] = np.array([PITCH_LENGTH - 0.5, PITCH_WIDTH / 2])
        active = np.stack([self._active(0), self._active(1)])
        top = self._physique()[0]
        for _ in range(25):
            self.prev = self.pos.copy()
            self.pos, self.speed = MovementModel.step(self.pos, targets, top, self.fitness, active)
            self.pos, self.speed = settle(self.pos), settle(self.speed)
            self.ball = self.pos[k, i].copy()
            self._record_frame()
            self.t += 1
        self.ball = spot.copy()
        keeper = np.mean([self._a(opp, g, a) for a in ("diving", "reflexes", "positioning")]) if g is not None else 0.5
        p = float(np.clip(0.76 + 0.3 * (self._a(k, i, "penalties") - 0.7) - 0.25 * (keeper - 0.88), 0.55, 0.92))
        r, r2 = self.rng.random(), self.rng.random()
        outcome = "goal" if r < p else ("saved" if r2 < 0.65 else ("off_target" if r2 < 0.9 else "post"))
        aim_y = PITCH_WIDTH / 2 + uniform(self.rng, -3.4, 3.4) + (self.rng.choice([-1, 1]) * 5 if outcome == "off_target" else 0)
        gk_at = self.pos[opp, g].copy() if g is not None else np.array([PITCH_LENGTH, PITCH_WIDTH / 2])
        shot = self._emit("shot", k, i, location=spot.copy(), end_location=np.array([PITCH_LENGTH, aim_y]),
                          shot_outcome=outcome, xg=round(p, 4), body_part=f"{self.attr[self._pid(k, i)]['foot']}_foot",
                          shot_technique="normal", keeper_location=gk_at, shootout_round=rnd,
                          shot_end_height_m=round(float(uniform(self.style_rng, 0.1, 2.3)), 2),
                          ball_speed_kmh=round(float(np.clip(80 + 40 * self._a(k, i, "shot_power") + normal(self.style_rng, 0, 6), 60, 135)), 1))
        shot["possession_id"], shot["play_pattern"] = None, "penalty"
        if g is not None and outcome in ("goal", "saved"):
            ge = self._emit("goalkeeper", opp, g, location=gk_at, keeper_action="goal_conceded" if outcome == "goal" else "shot_saved",
                            keeper_technique="diving")
            ge["possession_id"] = None
            self._link(shot, ge)
        for _ in range(10):                                   # back to the centre circle
            self.prev = self.pos.copy()
            self.pos, self.speed = MovementModel.step(self.pos, circle, top, self.fitness, active)
            self.pos, self.speed = settle(self.pos), settle(self.speed)
            self._record_frame()
            self.t += 1
        return int(outcome == "goal")

    def run(self) -> SimOutput:
        self.play()
        self._finalise()
        f = self.frames
        final = self.match.model_copy(update={
            "status": "finished", "clock": self.t - 1, "period": self.periods[-1].period, "periods": self.periods,
            "score": Score(home=self.score[0], away=self.score[1],
                           home_penalties=self.shootout[0] if self.shootout else None,
                           away_penalties=self.shootout[1] if self.shootout else None),
            "decided_by": self.decided_by,
        })
        return SimOutput(final, self.events, np.array(f["t"]), np.array(f["period"]), np.array(f["poss"]),
                         np.array(f["ball"]), f["owner"], f["ids"], np.array(f["pos"]), np.array(f["speed"]),
                         np.array(f["fit"]))

    def _finalise(self) -> None:
        """Set play patterns per possession (ATTR-003), including counter-attacks."""
        by_pid: dict[int, list[dict]] = {}
        for e in self.events:
            if e.get("possession_id"):
                by_pid.setdefault(e["possession_id"], []).append(e)
        side_index = {"home": 0, "away": 1}
        for pid, evs in by_pid.items():
            team = None
            for e in evs:
                if e["type"] in ("pass", "carry", "shot", "dribble"):
                    team = e["team"]
                    break
            pattern = "open_play"
            for e in evs:
                hint = e.pop("play_pattern_hint", None)
                if e["type"] == "pass" and e.get("pass_type") in ("corner", "free_kick", "throw_in", "goal_kick", "kick_off"):
                    pattern = e["pass_type"]
                    break
                if hint:
                    pattern = hint
                    break
                if e["type"] in ("pass", "carry", "shot", "dribble"):
                    break
            if pattern == "open_play" and team is not None:
                k = side_index[team]
                own = [e for e in evs if e["team"] == team and e.get("location")]
                if own:
                    start_t = own[0]["t"]
                    start_x = self._view(np.array(own[0]["location"]), k)[0]
                    passes = 0
                    progressions = 0
                    broke = False
                    for e in own:
                        if e["type"] in ("pass", "carry"):
                            progressions += 1
                            if progressions <= 2 and e.get("_break"):
                                broke = True
                        if e["type"] == "pass":
                            passes += 1
                        loc = e.get("end_location") or e["location"]
                        if self._view(np.array(loc), k)[0] >= COUNTER_REACH:
                            if start_x < PITCH_LENGTH / 2 and e["t"] - start_t <= COUNTER_SECONDS and passes <= 4 and broke:
                                pattern = "counter"
                            break
            for e in evs:
                e["play_pattern"] = pattern
        for e in self.events:
            e.pop("play_pattern_hint", None)


def simulate(match: Match, seed: int | None = None, params: Params | None = None,
             plants: list[PlantSpec] | None = None, context_effects: bool | None = None) -> SimOutput:
    return Engine(match, seed, params, plants, context_effects).run()


__all__ = ["Engine", "Params", "SimOutput", "simulate", "xg_model", "threat_value", "zone_of"]
