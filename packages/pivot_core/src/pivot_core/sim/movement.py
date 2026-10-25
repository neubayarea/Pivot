"""Movement model (B11): where each of the 22 players wants to be every second.

Each player has an anchor in the team's formation (team view, CONV-002). Every second
the anchor is moved as a block:

- vertically, around a back-line height set by the team's `line_height` and the ball's
  position; the block stretches in possession and compresses out of it;
- horizontally, towards the ball side, wider in possession (`width`) and narrower out of it;
- by individual instructions (overlap, stay back, cut inside, ...);
- attackers do not run beyond the opponents' last line by more than a step, so offside
  happens only occasionally;
- out of possession the one or two nearest players press the ball carrier, depending on
  `press` and on where the ball is; right after losing the ball one more player joins in.

Players then move towards their target (REAL-014): each has his own top speed from his pace
(about 7.8 m/s for the slowest, 10.5 for the fastest), lowered by fatigue; nobody reaches it in
one second (his acceleration caps how much faster he can go each second); and after a run of
sprinting he has to jog for a while before he can sprint again. A slowly changing personal
offset keeps lines from looking robotic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..domain import TeamSheet, TeamTactics
from ..domain.common import PITCH_LENGTH, PITCH_WIDTH
from .formations import DEFENDER_ROLES, WIDE_DEFENDERS

# Back-line x with the ball at halfway (team view); the engine adds Params.line_lift, tuned so
# defenders' defensive actions happen about 30 m from goal, as in the Premier League (REAL-015).
LINE_HEIGHT = {"low": 22.0, "mid": 28.0, "high": 38.0}
WIDTH_IN = {"narrow": 0.9, "normal": 1.05, "wide": 1.2}
PRESS_PLAYERS = {"low": 1, "mid": 1, "high": 2}
NEAR_OWN_BOX = 25.0                       # ball this close to our goal: at least two close down
# Press when the ball is closer to our goal than this; PPDA about 9 overall (REAL-015).
PRESS_ZONE = {"low": 40.0, "mid": 60.0, "high": PITCH_LENGTH}
PRESS_LEVELS = ("low", "mid", "high")
BOX_ATTACK_FROM = 60.0                    # ball this far up (team view): forwards start attacking the box
# Anchor x out of possession, unless pressing high: wide forwards and the playmaker drop into
# midfield, central midfielders sit level with the holding player.
DEFENDING_X = {"LW": 48.0, "RW": 48.0, "AM": 52.0, "CM": 43.0}
BOX_RUNNERS = {"ST": 1.0, "AM": 0.8, "LW": 1.0, "RW": 1.0, "LM": 0.5, "RM": 0.5, "CM": 0.35}
SPRINT_MS = 7.0                           # a sprint: 7 m/s (25 km/h) or more, as in the player ratings
TOP_MS = (7.8, 10.5)                      # top speed of the slowest and the fastest player (REAL-014)
ACCEL_MS2 = (2.5, 3.0)                    # speed gained per second: base + weight x acceleration rating
RECOVER_MS = 6.5                          # top speed while recovering from a run of sprints
BURST_S, RECOVERED_S = 6.0, 1.0           # seconds sprinting before he must recover; recovered below
CRUISE_MS = 6.0                           # repositioning pace; only a player with a reason sprints
_FAR_CORNER = np.array([PITCH_LENGTH, PITCH_WIDTH])
_ON_PITCH_LO = np.array([0.5, 0.5])
_ON_PITCH_HI = np.array([PITCH_LENGTH - 0.5, PITCH_WIDTH - 0.5])
_OFFSET_SD = np.array([1.8, 1.5])          # personal drift around the target, x and y (metres)


@dataclass
class TeamShape:
    """Per-team state the movement model needs, rebuilt whenever the sheet or tactics change."""

    side: int                                 # 0 home, 1 away
    player_ids: list[str | None]              # by slot index 0-10; None = sent off, slot empty
    roles: list[str]
    anchors: np.ndarray                       # (11, 2) team view
    tactics: TeamTactics
    pace: np.ndarray                          # (11,) 0-1
    instructions: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_sheet(cls, side: int, sheet: TeamSheet, tactics: TeamTactics,
                   pace_by_player: dict[str, float]) -> "TeamShape":
        slots = sorted(sheet.starters, key=lambda s: s.slot)
        ids: list[str | None] = [None] * 11
        roles = ["CB"] * 11
        anchors = np.zeros((11, 2))
        for s in slots:
            i = s.slot - 1
            ids[i], roles[i] = s.player_id, s.role
            anchors[i] = s.anchor
        pace = np.array([pace_by_player.get(p, 0.6) if p else 0.0 for p in ids])
        slot_of = {p: i for i, p in enumerate(ids) if p}
        instr = {slot_of[i.player_id]: i.instruction for i in tactics.instructions if i.player_id in slot_of}
        return cls(side, ids, roles, anchors, tactics, pace, instr)

    @property
    def active(self) -> np.ndarray:
        return np.array([p is not None for p in self.player_ids])


def to_view(p: np.ndarray, side: int) -> np.ndarray:
    """Absolute pitch coordinates to the team view of `side` (works on (..., 2) arrays)."""
    if side == 0:
        return p
    return _FAR_CORNER - p


from_view = to_view   # the transform is its own inverse


def top_speed(pace: np.ndarray | float) -> np.ndarray:
    """Top speed in m/s from the 0-1 pace rating (REAL-014)."""
    return TOP_MS[0] + (TOP_MS[1] - TOP_MS[0]) * np.clip((np.asarray(pace, dtype=float) - 0.45) / 0.5, 0.0, 1.0)


def clip1(x: float, lo: float, hi: float) -> float:
    """np.clip for a single number, without numpy's per-call cost. Same result in every case,
    including a value equal to a bound (the value comes back, so -0.0 stays -0.0) and NaN."""
    if x != x:
        return x
    x = x if x >= lo else lo
    return x if x <= hi else hi


@dataclass
class MovementModel:
    rng: np.random.Generator
    offsets: np.ndarray = field(default_factory=lambda: np.zeros((2, 11, 2)))
    offset_until: np.ndarray = field(default_factory=lambda: np.zeros((2, 11)))
    run_until: np.ndarray = field(default_factory=lambda: np.zeros((2, 11)))
    pressers: set = field(default_factory=set)   # (team, slot) sent to close down the ball this second
    line_shift: list = field(default_factory=lambda: [0.0, 0.0])   # metres, set by the engine's game state
    press_shift: list = field(default_factory=lambda: [0, 0])      # press levels up (+) or down (-)
    offside_slack: float = 0.5                   # metres a forward may drift beyond the last defender
    urgent: np.ndarray = field(default_factory=lambda: np.zeros((2, 11), dtype=bool))   # may sprint this second
    line_lift: float = 0.0                       # metres added to every LINE_HEIGHT (Params.line_lift)

    def _refresh_offsets(self, t: int) -> None:
        due = self.offset_until <= t
        n = int(due.sum())
        if n:
            # = rng.normal(0, [1.8, 1.5], size=(n, 2)): same draws, same numbers, without its argument checks
            self.offsets[due] = self.rng.standard_normal((n, 2)) * _OFFSET_SD
            self.offset_until[due] = t + self.rng.integers(10, 25, size=n)

    def targets(self, t: int, shapes: tuple[TeamShape, TeamShape], pos: np.ndarray, ball: np.ndarray,
                possession: int | None, carrier: tuple[int, int] | None, loose: bool,
                last_loss_t: tuple[int, int], flight_target: tuple[int, int, np.ndarray] | None) -> np.ndarray:
        self._refresh_offsets(t)
        self.pressers = set()
        self.urgent = np.zeros((2, 11), dtype=bool)
        out = np.empty_like(pos)
        active = (shapes[0].active, shapes[1].active)
        for k, shape in enumerate(shapes):
            out[k] = self._team_targets(t, k, shape, active[k], active[1 - k], pos, ball, possession, carrier,
                                        loose, last_loss_t[k])
        if flight_target is not None:
            k, i, end = flight_target
            out[k, i] = end
            self.urgent[k, i] = True
        return out

    def _team_targets(self, t: int, k: int, shape: TeamShape, active: np.ndarray, opp_active: np.ndarray,
                      pos: np.ndarray, ball: np.ndarray, possession: int | None, carrier: tuple[int, int] | None,
                      loose: bool, last_loss: int) -> np.ndarray:
        # Runs twice every second of play. The per-player sums are done on plain floats: for 11
        # numbers that is far cheaper than a numpy call each, and + - * / give exactly the same
        # doubles, so every seed plays as before. Distances stay with np.hypot.
        tac = shape.tactics
        b = to_view(ball, k)
        bx, by = float(b[0]), float(b[1])
        in_poss = possession == k

        if in_poss:
            line = clip1(LINE_HEIGHT[tac.line_height] + self.line_lift + 6 + 0.45 * (bx - 40), 15.0, 62.0)
            depth, width, follow = 1.25, WIDTH_IN[tac.width], 0.2
        else:
            # even a deep block holds its line around the penalty spot, not on the six-yard box
            line = clip1(LINE_HEIGHT[tac.line_height] + self.line_lift + 0.3 * (bx - 52.5), 11.0, 55.0)
            # the nearer the ball to our goal, the tighter the gap between the lines (B12)
            depth, width, follow = 0.55 + 0.25 * clip1((bx - 25.0) / 35.0, 0.0, 1.0), 0.72, 0.4

        follow_y = follow * (by - 34)
        anchors = shape.anchors.tolist()
        if not in_poss and tac.press != "high":
            # Out of possession the wide forwards and the playmaker drop into the midfield line:
            # a 4-3-3 defends as 4-1-4-1 or 4-5-1, a 4-2-3-1 as 4-4-1-1 (B12, REAL-003).
            anchors = [[min(ax, DEFENDING_X.get(r, ax)), ay] for (ax, ay), r in zip(anchors, shape.roles)]
        tx = [line + (ax - 26.0) * depth for ax, _ in anchors]
        ty = [34 + (ay - 34) * width + follow_y for _, ay in anchors]

        for i, instr in shape.instructions.items():
            if instr in ("get_forward", "overlap") and in_poss:
                tx[i] += 10
            elif instr == "stay_back" or instr == "sit_deeper":
                tx[i] -= 7
            elif instr == "cut_inside" and in_poss:
                ty[i] = 34 + (ty[i] - 34) * 0.6
            elif instr == "stay_wide" and in_poss:
                ty[i] = 34 + (ty[i] - 34) * 1.15

        # Attacking the box (B12): with the ball in the final third the forwards leave their
        # anchors for the box, the far-side winger for the back post; wide midfielders go half way.
        if in_poss and bx > BOX_ATTACK_FROM:
            pull = min((bx - BOX_ATTACK_FROM) / 25, 1.0)
            for i, r in enumerate(shape.roles):
                if r not in BOX_RUNNERS:
                    continue
                if r == "ST":
                    gx, gy = 96.0, 34 + 0.15 * (by - 34)
                elif r == "AM":
                    gx, gy = 86.0, 34 + 0.3 * (by - 34)
                elif r == "CM":                            # a late run to the edge of the box, in his channel
                    gx, gy = 84.0, 34 + (9.0 if ty[i] > 34 else -9.0)
                elif (ty[i] - 34) * (by - 34) < 0:         # ball on the other flank: back post
                    gx, gy = 95.0, 34 + (6.0 if ty[i] > 34 else -6.0)
                else:                                      # ball on his flank: come inside off the line
                    gx, gy = tx[i], 34 + (ty[i] - 34) * 0.6
                weight = pull * BOX_RUNNERS[r]
                tx[i] += (gx - tx[i]) * weight
                ty[i] += (gy - ty[i]) * weight
                self.urgent[k, i] = True                   # attacking the box is done at full speed

        # Game state (B12): out of possession the engine shifts the block up when chasing a game
        # and down when protecting a lead or a man short. With the ball the shape stays as it is.
        shift = self.line_shift[k]
        if shift and not in_poss:
            tx = [x + shift if r != "GK" else x for x, r in zip(tx, shape.roles)]

        # Forward runs in possession: attackers and midfielders now and then push on.
        if in_poss:
            starting = (self.run_until[k] <= t) & (self.rng.random(11) < 0.03)
            for i in np.flatnonzero(starting):
                if shape.roles[i] not in DEFENDER_ROLES or shape.roles[i] in WIDE_DEFENDERS:
                    self.run_until[k, i] = t + self.rng.integers(3, 7)
            for i in np.flatnonzero(self.run_until[k] > t):
                tx[i] += 9
                self.urgent[k, i] = True                   # a run in behind is a sprint
        elif t - last_loss <= 8:
            # just lost the ball: whoever is caught upfield of it races back (REAL-014)
            own_x = pos[k, :, 0] if k == 0 else PITCH_LENGTH - pos[k, :, 0]
            self.urgent[k] |= own_x > bx + 5

        # Do not stand far beyond the opponents' last line.
        opp_x = sorted((x if k == 0 else PITCH_LENGTH - x
                        for x, on in zip(pos[1 - k, :, 0].tolist(), opp_active.tolist()) if on), reverse=True)
        last_line = opp_x[1] if len(opp_x) > 1 else PITCH_LENGTH
        cap = max(last_line, bx) + self.offside_slack
        target = np.array([[min(x, cap) + ox, y + oy] for x, y, (ox, oy) in zip(tx, ty, self.offsets[k].tolist())])

        # Goalkeeper.
        for i, r in enumerate(shape.roles):
            if r == "GK":
                target[i, 0] = clip1(3 + 0.1 * bx * (1.5 if in_poss else 1.0), 2.0, 20.0)
                target[i, 1] = 34 + 0.2 * (by - 34)

        # Pressing and chasing loose balls.
        if loose:
            d = self._distances_to_ball(k, shape, active, pos, b)
            for i in np.argsort(d)[:2]:
                target[i] = b
                self.urgent[k, i] = True
        elif not in_poss and carrier is not None:
            press = PRESS_LEVELS[min(max(PRESS_LEVELS.index(tac.press) + self.press_shift[k], 0), 2)]
            n = PRESS_PLAYERS[press]
            counter = t - last_loss <= 5
            if counter:
                n += 1
            if bx <= NEAR_OWN_BOX:
                n = max(n, 2)                      # every team closes down near its own box
            if counter or bx <= PRESS_ZONE[press]:
                d = self._distances_to_ball(k, shape, active, pos, b)
                towards_goal = np.array([-2.5, 0.0])   # close down, do not run into him
                for i in np.argsort(d)[:n]:
                    target[i] = b + towards_goal
                    self.pressers.add((k, int(i)))
                    self.urgent[k, i] = True
        np.minimum(np.maximum(target, _ON_PITCH_LO), _ON_PITCH_HI, out=target)
        return from_view(target, k)

    @staticmethod
    def _distances_to_ball(k: int, shape: TeamShape, active: np.ndarray, pos: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Each outfield player's distance to the ball (team view); inf for keepers and empty slots."""
        own = to_view(pos[k], k)
        outfield = np.array([r != "GK" for r in shape.roles]) & active
        return np.where(outfield, np.hypot(*(own - b).T), np.inf)

    @staticmethod
    def step(pos: np.ndarray, target: np.ndarray, top: np.ndarray, fitness: np.ndarray, active: np.ndarray,
             speed: np.ndarray | None = None, accel: np.ndarray | None = None,
             urgent: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Move every player one second towards the target. `top` is each player's top speed in
        m/s right now (pace, and whether he is recovering from sprints); `speed` and `accel`, when
        given, cap how much faster than last second he can go; players not `urgent` reposition at
        no more than CRUISE_MS. Returns new positions and speeds."""
        delta = target - pos
        dist = np.hypot(delta[..., 0], delta[..., 1])
        vmax = top * (0.7 + 0.3 * fitness)
        if urgent is not None:
            vmax = np.where(urgent, vmax, np.minimum(vmax, CRUISE_MS))
        # Jog when the target is close, sprint only when it is far.
        desired = np.minimum(vmax, 0.3 + 0.35 * dist)
        if speed is not None:
            desired = np.minimum(desired, speed + accel)
        move = np.minimum(dist, desired)
        scale = np.divide(move, dist, out=np.zeros_like(dist), where=dist > 1e-9)
        new = pos + delta * scale[..., None]
        speed = np.where(active, move, 0.0)
        new = np.where(active[..., None], new, pos)
        return new, speed
