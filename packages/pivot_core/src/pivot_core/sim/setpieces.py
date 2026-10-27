"""Set-piece positions (Ax44, #245): where the 22 stand while a corner or a free kick is set up.

The numbers come from the Premier League (StatsBomb open data 2015/16, shot freeze frames, and
coaching and analysis write-ups); docs/set-pieces.md has the table and the sources.

Corners (team view of the side taking it; "near" is the corner's side of the goal):

- attackers: `players_forward_on_corners` (one either way) in the box: in front of the keeper,
  near post, far post, penalty spot, central, then late runners; the centre-backs and the
  striker go first. One or two on the edge of the box for the second ball, sometimes one short
  by the flag; the rest (two or three) stay back near halfway against the counter;
- defenders: `players_back_on_corners` (forwards first) stay up near halfway; the rest defend the
  box the team's way (`corner_defence`): zonal = six zones plus two markers, mixed = four zones
  (two near post, one central, one far post) and markers on the rest, man = two zones and a marker
  on every attacker in the box. A marker stands a metre goal-side of his man and follows him. Now
  and then a man on the near or far post. Everyone else on the edge of the box. Nobody within
  9.15 m of the corner arc;
- the keeper on his line, a metre or so off it.

Free kicks:

- within shooting range (< 32 m, in front of goal): a wall 9.15 m from the ball covering the
  near post, its size by distance (about 6 inside 20 m, 5 at 20-25 m, 4 at 25-30 m, 2 beyond,
  one fewer from a wide angle); the keeper covers the other side; the other defenders hold a line
  around the penalty spot, marking four or five attackers; two attackers stay back;
- from the final third, out wide or further out: one or two in the wall, defenders hold a line
  in the box, five attackers on it;
- anywhere else play goes on as it was; only the opponents step back 9.15 m from the ball.

These are the positions in the tracking frames: what the match page shows. The engine resolves the
kick, the header and the shot from its own positions as before (calibrated against the Premier
League), so the run of play, the events and the score of every seed stay as they were. After the
kick whoever may get the ball heads for where the engine has him; the rest hold their spots while
the ball is around the box, then jog back. Nobody is shown faster than his own top speed (REAL-014),
so now and then a pass reaches a man a second before he is shown arriving.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..domain.common import PITCH_LENGTH, PITCH_WIDTH
from .movement import TeamShape, from_view, norm, normal, settle, to_view, uniform

GOAL_V = np.array([PITCH_LENGTH, PITCH_WIDTH / 2])        # the goal attacked, in the kicking side's view
POST = 3.66                                               # goal centre to post
KEEP_OFF = 9.15                                           # Laws 13 and 17: opponents this far from the ball
SHOOTING_M = 32.0                                         # free kick this close, in front of goal: a wall
WALL_GAP = 0.6                                            # shoulder to shoulder
# Shown speeds (m/s): setting up, following a man, jogging back after the kick (under the 7 m/s
# that counts as a sprint), going for the ball.
WALK_MS, MARK_MS, RUN_MS, CHASE_MS = 5.5, 6.5, 6.5, 10.5
RELEASE_S = 120                                           # after this the shown players are where the engine has them
INVOLVED_M = 15.0                                         # after the kick, anyone the engine has this near the ball
                                                          # may get it soon: he heads for where the engine has him
STAY_S, STAY_M = 8, 25.0                                  # after the kick the rest hold their spots this long, while the
                                                          # ball is within this many metres of the goal line

# Corner spots, (metres from the goal line, metres towards the near side from the goal centre).
ATTACK_BOX = ((1.6, 0.8), (5.5, 4.5), (6.0, -5.0), (10.5, 0.5), (8.0, -1.5), (12.0, -7.0), (8.5, 7.5))
ATTACK_EDGE = ((19.0, -2.0), (18.0, 9.0))
SHORT = (6.0, 27.0)                                       # short option, about 9 m from the flag
REST = ((55.0, -12.0), (55.0, 12.0), (60.0, 0.0), (48.0, 0.0))   # rest defence, distance from the goal line
# Zones in the order a team fills them: the near-post triangle and the six-yard line first (Arsenal:
# two near post, one central, one far post), then the penalty-spot area.
ZONES = ((6.0, 5.5), (3.5, 5.5), (6.5, 0.0), (6.5, -4.5), (10.0, 2.5), (10.5, -4.0), (6.5, 9.5), (6.0, -8.0))
DEF_EDGE = ((17.5, 2.0), (16.5, -8.0), (15.0, 10.0))
UPFIELD = ((62.0, 0.0), (60.0, -12.0), (60.0, 12.0))     # left up for the counter
NEAR_POST_MAN, FAR_POST_MAN = (0.8, 3.2), (0.8, -3.2)
POST_SHARE = (0.355, 0.312)                               # a man on the near / far post (PL 2015/16 freeze frames)
ZONAL = {"zonal": 6, "mixed": 4, "man": 2}
# Box picking order: who goes up for a corner, who stays back.
UP_ORDER = {"ST": 0, "CB": 1, "AM": 2, "LW": 2, "RW": 2, "CM": 3, "LM": 3, "RM": 3, "LWB": 4, "RWB": 4,
            "DM": 5, "LB": 6, "RB": 6}
STAY_UP = {"ST": 0, "LW": 1, "RW": 1, "AM": 1, "LM": 2, "RM": 2, "CM": 3}
# Wall size by the free kick's distance from goal (PL 2015/16: 6.5, 5.0, 3.8, 2.0 in the line).
WALL_BY_DISTANCE = ((20.0, 6), (25.0, 5), (30.0, 4), (99.0, 2))


def _p(d: float, near: float, s: float) -> np.ndarray:
    """A spot `d` metres off the goal line, `near` metres towards the near side (s = +1 or -1)."""
    return np.array([PITCH_LENGTH - d, PITCH_WIDTH / 2 + s * near])


def _assign(pos: np.ndarray, who: list[int], spots: list[np.ndarray], bias=None) -> dict[int, int]:
    """Greedy nearest assignment of players `who` (positions `pos`) to spots: the closest pair
    first, a tie to the lower slot and spot. `bias(i, n)` adds metres to a pairing."""
    out: dict[int, int] = {}
    if not who or not spots:
        return out
    cost = np.array([[float(norm(pos[i] - sp)) + (bias(i, n) if bias else 0.0) for n, sp in enumerate(spots)]
                     for i in who])
    for _ in range(min(len(who), len(spots))):
        r, c = divmod(int(np.argmin(cost)), cost.shape[1])
        out[who[r]] = c
        cost[r, :] = np.inf
        cost[:, c] = np.inf
    return out


def _pick(roles: list[str], who: list[int], order: dict[str, int], n: int) -> list[int]:
    """The first `n` of `who` in role order (unlisted roles last), slot order within a role."""
    return sorted(who, key=lambda i: (order.get(roles[i], 9), i))[:max(n, 0)]


@dataclass
class Plan:
    """Shown targets for one set piece, in the kicking side's view. `mark` maps a defender's slot to
    the attacker's slot he follows; spots are fixed. Slots in neither follow the engine."""

    kind: str
    team: int
    spots: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)
    mark: dict[int, int] = field(default_factory=dict)
    jostle: set = field(default_factory=set)              # (side, slot) in the box: shuffle a little


def corner_plan(rng: np.random.Generator, k: int, shapes: tuple[TeamShape, TeamShape], pos: np.ndarray,
                ball: np.ndarray, taker: int) -> Plan:
    att, dfn = shapes[k], shapes[1 - k]
    av, dv, bv = to_view(pos[k], k), to_view(pos[1 - k], k), to_view(ball, k)
    s = 1.0 if bv[1] > PITCH_WIDTH / 2 else -1.0
    plan = Plan("corner", k)
    sp = att.tactics.set_pieces

    # Attackers: box, short, edge, rest defence.
    pool = [i for i in range(11) if att.active[i] and att.roles[i] != "GK" and i != taker]
    n_box = int(np.clip(sp.players_forward_on_corners + rng.choice((-1, 0, 0, 1)), 4, len(ATTACK_BOX)))
    short = rng.random() < 0.2
    n_edge = 2 if rng.random() < 0.25 else 1
    keep = 3 if rng.random() < 0.4 else 2
    while n_box + short + n_edge + keep > len(pool) and (n_edge or short or n_box > 3 or keep > 1):
        if n_edge:
            n_edge -= 1
        elif short:
            short = False
        elif keep > 1:
            keep -= 1
        else:
            n_box -= 1
    # The engine plays the corner to someone it has in the box, so they all go in first; the
    # striker and the centre-backs fill the box up.
    in_box = [i for i in pool if PITCH_LENGTH - float(av[i][0]) < 20.0 and abs(float(av[i][1]) - PITCH_WIDTH / 2) < 22]
    box = in_box[:n_box] + _pick(att.roles, [i for i in pool if i not in in_box], UP_ORDER, n_box - len(in_box))
    rest_pool = [i for i in pool if i not in box]
    back = sorted(rest_pool, key=lambda i: (-UP_ORDER.get(att.roles[i], 9), i))[:keep]
    mid = [i for i in rest_pool if i not in back]
    box_spots = [_p(d, n, s) for d, n in ATTACK_BOX[:len(box)]]
    box_at = _assign(av, box, box_spots)
    for i, n in box_at.items():
        plan.spots[(k, i)] = box_spots[n]
        plan.jostle.add((k, i))
    others = ([_p(*SHORT, s)] if short else []) + [_p(d, n, s) for d, n in ATTACK_EDGE[:n_edge]]
    for i, n in _assign(av, mid, others).items():
        plan.spots[(k, i)] = others[n]
    rest = [np.array([PITCH_LENGTH - d, PITCH_WIDTH / 2 + s * n]) for d, n in REST]
    for i, n in _assign(av, back + [i for i in mid if (k, i) not in plan.spots], rest).items():
        plan.spots[(k, i)] = rest[n]

    # Defenders: left up, then zones, markers, post men, edge.
    pool = [j for j in range(11) if dfn.active[j] and dfn.roles[j] != "GK"]
    n_up = int(min(dfn.tactics.set_pieces.players_back_on_corners, max(len(pool) - 6, 0)))
    up = _pick(dfn.roles, pool, STAY_UP, n_up)
    up_spots = [np.array([PITCH_LENGTH - d, PITCH_WIDTH / 2 + s * n]) for d, n in UPFIELD[:len(up)]]
    for j, n in _assign(dv, up, up_spots).items():
        plan.spots[(1 - k, j)] = up_spots[n]
    home = [j for j in pool if j not in up]
    scheme = dfn.tactics.set_pieces.corner_defence
    n_zone = min(ZONAL[scheme], len(home))
    zone_spots = [_p(d, n, s) for d, n in ZONES[:n_zone]]
    # a man on a post now and then, out of the zonal quota
    for share, man in zip(POST_SHARE, (NEAR_POST_MAN, FAR_POST_MAN)):
        if zone_spots and rng.random() < share:
            zone_spots[-1 if len(zone_spots) > 1 else 0] = _p(*man, s)
            zone_spots = [zone_spots[-1]] + zone_spots[:-1]
    left = len(home) - len(zone_spots)
    targets = sorted(box, key=lambda i: box_at[i])        # in front of the keeper, near post, far post, ...
    if scheme == "zonal":
        targets = targets[1:3] if len(targets) > 2 else targets      # the two biggest threats, not the screen
    marked = targets[:left]
    left -= len(marked)
    guard = []
    if short and left:                                    # someone goes out to the short man, 9.15 m off the arc
        guard = [_p(*SHORT, s) + (GOAL_V - _p(*SHORT, s)) / float(norm(GOAL_V - _p(*SHORT, s))) * 1.0]
        left -= 1
    edge = [_p(d, n, s) for d, n in DEF_EDGE[:max(left, 0)]]
    extra = left - len(edge)
    zone_spots += [_p(d, n, s) for d, n in ZONES[n_zone:n_zone + max(extra, 0)]]
    fixed = zone_spots + guard + edge
    mark_spots = [plan.spots[(k, i)] + (GOAL_V - plan.spots[(k, i)]) / max(float(norm(GOAL_V - plan.spots[(k, i)])), 1.0)
                  for i in marked]
    pairs = _assign(dv, home, fixed + mark_spots,
                    bias=lambda j, n: -4.0 if dfn.roles[j] == "CB" and n < len(zone_spots) else 0.0)
    for j, n in pairs.items():
        if n < len(fixed):
            plan.spots[(1 - k, j)] = fixed[n]
        else:
            plan.mark[j] = marked[n - len(fixed)]
        plan.jostle.add((1 - k, j))

    _keeper(rng, plan, dfn, _p(1.0 + abs(normal(rng, 0.0, 0.35)), normal(rng, -0.3, 0.5), s), k)
    return _spread(rng, plan)


def free_kick_plan(rng: np.random.Generator, k: int, shapes: tuple[TeamShape, TeamShape], pos: np.ndarray,
                   ball: np.ndarray, taker: int) -> Plan:
    att, dfn = shapes[k], shapes[1 - k]
    av, dv, bv = to_view(pos[k], k), to_view(pos[1 - k], k), to_view(ball, k)
    plan = Plan("free_kick", k)
    dist = float(norm(bv - GOAL_V))
    wide = abs(float(bv[1]) - PITCH_WIDTH / 2)
    shooting = dist < SHOOTING_M and wide < 18
    crossing = not shooting and bv[0] >= 70 and dist < 45
    if not (shooting or crossing):
        return plan                                       # play on as it was; only the 9.15 m rule applies
    s = 1.0 if bv[1] > PITCH_WIDTH / 2 else -1.0
    d_line = PITCH_LENGTH - float(bv[0])

    # The wall: the end man on the line from the ball to just outside the near post, the rest
    # shoulder to shoulder towards the middle of the goal.
    if shooting:
        n_wall = next(n for hi, n in WALL_BY_DISTANCE if dist < hi) + int(rng.choice((-1, 0, 0, 1)))
        n_wall -= 1 if wide > 12 else 0
    else:
        n_wall = 2 if dist < 35 and rng.random() < 0.5 else 1
    pool = [j for j in range(11) if dfn.active[j] and dfn.roles[j] != "GK"]
    n_wall = int(np.clip(n_wall, 1, max(len(pool) - 3, 1)))
    post = np.array([PITCH_LENGTH, PITCH_WIDTH / 2 + s * (POST + 0.4)])
    u = (post - bv) / float(norm(post - bv))
    across = np.array([-u[1], u[0]])
    if float(across[1]) * s > 0:                          # point the wall towards the middle of the goal
        across = -across
    at = KEEP_OFF + uniform(rng, 0.05, 0.35)
    wall = [bv + u * at + across * (WALL_GAP * w) for w in range(n_wall)]
    pairs = _assign(dv, pool, wall, bias=lambda j, n: 12.0 if dfn.roles[j] == "CB" else 0.0)
    for j, n in pairs.items():
        plan.spots[(1 - k, j)] = wall[n]

    # The line: around the penalty spot for a shot at goal, deeper the closer a cross comes from.
    line = (float(np.clip(d_line - 11.0, 9.0, 15.5)) if shooting
            else float(np.clip(0.5 * d_line + 5.0, 9.0, 16.5)))
    # A free kick is often played short at once: the man the engine has nearest the ball stays where
    # it has him (the man over the ball), and the box is filled by those nearest it, so a pass
    # seldom goes to someone shown far away.
    pool = [i for i in range(11) if att.active[i] and att.roles[i] != "GK" and i != taker]
    near = sorted((i for i in pool if float(norm(av[i] - bv)) < 12.0), key=lambda i: float(norm(av[i] - bv)))[:1]
    pool = [i for i in pool if i not in near]
    n_box = (4 if shooting else 5) + int(rng.choice((-1, 0, 0, 1)))
    over_ball = shooting and not near and rng.random() < 0.6
    by_wall = shooting and n_wall >= 3 and rng.random() < 0.5
    keep = 2
    n_box = int(np.clip(n_box, 2, max(len(pool) - keep - over_ball - by_wall - 1, 2)))
    centre = PITCH_WIDTH / 2 + (0.0 if shooting else s * 3.0)
    ys = np.linspace(-9.0, 9.0, n_box) if n_box > 1 else np.zeros(1)
    box_spots = [np.array([PITCH_LENGTH - line + uniform(rng, -0.8, 0.8), centre + float(y)]) for y in ys]
    box_at = _assign(av, pool, box_spots)
    box = sorted(box_at)
    for i, n in box_at.items():
        plan.spots[(k, i)] = box_spots[n]
        plan.jostle.add((k, i))
    rest_pool = [i for i in pool if i not in box]
    back = sorted(rest_pool, key=lambda i: (float(av[i][0]), i))[:keep]      # the deepest stay back
    mid = [i for i in rest_pool if i not in back]
    others = []
    if over_ball:                                          # a second man over the ball
        others.append(bv + np.array([-1.2, -s * 1.2]))
    if by_wall:                                            # one beside the wall, the 1 m the law asks
        others.append(wall[-1] + across * 1.1)
    others.append(np.array([PITCH_LENGTH - max(line + 8.0, 19.0), PITCH_WIDTH / 2 - s * 4.0]))   # second ball
    for i, n in _assign(av, mid, others).items():
        plan.spots[(k, i)] = others[n]
    rest = [np.array([max(float(bv[0]) - 40.0, 45.0), PITCH_WIDTH / 2 + n]) for n in (-12.0, 12.0, 0.0, 24.0)]
    for i, n in _assign(av, back + [i for i in mid if (k, i) not in plan.spots], rest).items():
        plan.spots[(k, i)] = rest[n]

    # Defenders left: mark the box attackers goal-side, then hold zones in front of goal.
    home = [j for j in range(11) if dfn.active[j] and dfn.roles[j] != "GK" and (1 - k, j) not in plan.spots]
    up = _pick(dfn.roles, home, STAY_UP, 1 if rng.random() < 0.4 and len(home) > n_box + 1 else 0)
    for j in up:
        plan.spots[(1 - k, j)] = np.array([max(float(bv[0]) - 45.0, 40.0), PITCH_WIDTH / 2])
    home = [j for j in home if j not in up]
    marked = sorted(box, key=lambda i: abs(float(plan.spots[(k, i)][1]) - centre))[:len(home)]
    zones = [np.array([PITCH_LENGTH - max(line - 3.0, 5.5), PITCH_WIDTH / 2 + s * n]) for n in (3.0, -3.0, 8.0, -8.0)]
    zones = zones[:max(len(home) - len(marked), 0)]
    mark_spots = [plan.spots[(k, i)] + (GOAL_V - plan.spots[(k, i)]) / max(float(norm(GOAL_V - plan.spots[(k, i)])), 1.0)
                  for i in marked]
    for j, n in _assign(dv, home, zones + mark_spots).items():
        if n < len(zones):
            plan.spots[(1 - k, j)] = zones[n]
        else:
            plan.mark[j] = marked[n - len(zones)]
        plan.jostle.add((1 - k, j))

    # The keeper covers the side the wall does not, a metre or so off his line.
    _keeper(rng, plan, dfn, np.array([PITCH_LENGTH - 1.0 - abs(normal(rng, 0.3, 0.4)),
                                      PITCH_WIDTH / 2 - s * uniform(rng, 0.2, 1.2)]), k)
    return _spread(rng, plan)


def _spread(rng: np.random.Generator, plan: Plan) -> Plan:
    """No two corners alike: everyone in the box a little off his spot (half a metre or so)."""
    for key in sorted(plan.jostle):
        if key in plan.spots:
            plan.spots[key] = plan.spots[key] + normal(rng, 0.0, 0.6, 2)
    return plan


def _keeper(rng: np.random.Generator, plan: Plan, dfn: TeamShape, spot: np.ndarray, k: int) -> None:
    for j, r in enumerate(dfn.roles):
        if r == "GK" and dfn.active[j]:
            plan.spots[(1 - k, j)] = spot


class SetPieceView:
    """The positions the tracking frames show (see the module docstring). Holds no engine state:
    give it the engine's positions every second, get back what to record."""

    def __init__(self, rng: np.random.Generator):
        self.rng = rng
        self.shown: np.ndarray | None = None              # (2, 11, 2) while it differs from the engine
        self.plan: Plan | None = None
        self.plan_for: dict | None = None                 # the engine's restart the plan was made for
        self.draw = 0                                     # seeds the plan's own draws for that restart
        self.held = 0                                     # seconds the plan has been shown
        self.released = 0                                 # seconds since the kick
        self.last: np.ndarray | None = None               # what the last frame showed
        self.after = 0                                    # the side that took the last set piece
        self.involved = np.zeros((2, 11), dtype=bool)     # after the kick: who has gone for the ball
        self.won = False                                  # after the kick: the defending side has had the ball
        self.top = np.full((2, 11), CHASE_MS)             # each player's top speed this second

    def frame(self, t: int, shapes: tuple[TeamShape, TeamShape], pos: np.ndarray, speed: np.ndarray,
              top: np.ndarray, ball: np.ndarray, owner: tuple[int, int] | None, restart: dict | None,
              forced: dict | None, flight: dict | None) -> tuple[np.ndarray, np.ndarray]:
        """Positions and speeds to record for this second. `top` is each player's top speed (m/s):
        nobody is shown running faster."""
        self.top = top
        if restart is not None and restart["kind"] == "kick_off" and restart["period_start"]:
            self.shown, self.plan, self.plan_for = None, None, None      # a new half: everyone where the engine is
        elif restart is not None and restart["kind"] in ("corner", "free_kick"):
            if restart is not self.plan_for:
                self.plan_for, self.held = restart, 0
                self.draw = int(self.rng.integers(2 ** 31))
                if self.shown is None:                    # set off from where the last frame had them
                    self.shown = (self.last if self.last is not None else pos).copy()
            # Made again every second from where the engine has everybody, with the same draws, so
            # at the kick the men in the box are the ones the engine may play it to.
            maker = corner_plan if restart["kind"] == "corner" else free_kick_plan
            self.plan = maker(np.random.default_rng(self.draw), restart["team"], shapes, pos, restart["spot"],
                              restart["taker"])
            self._hold(shapes, pos, ball, restart["team"], restart["taker"])
        elif self.plan is not None and forced is not None and owner is not None and owner[0] == self.plan.team:
            self._hold(shapes, pos, ball, self.plan.team, owner[1])      # the kick is this coming second
        elif self.shown is not None:
            if self.plan is not None:
                self.after, self.involved, self.won = self.plan.team, np.zeros((2, 11), dtype=bool), False
                self.plan, self.plan_for = None, None
            self._release(t, pos, speed, ball, owner, flight)
        if self.shown is None:
            self.last = pos
            return pos, speed
        last = self.last if self.last is not None else pos
        # Nobody is shown running faster than his own top speed, not even the man on the ball: when
        # the ball reaches someone shown away from it, he gets there a second or two after it.
        move = self.shown - last
        far = norm(move)
        over = far > top
        if over.any():
            self.shown = settle(np.where(over[..., None], last + move * (top / np.maximum(far, 1e-9))[..., None],
                                         self.shown))
        if self.plan is None and bool((self.shown == pos).all()):
            self.shown, self.last = None, pos                 # everybody is back where the engine has him
            return pos, speed
        shown_speed = np.where(np.stack([shapes[0].active, shapes[1].active]), norm(self.shown - last), 0.0)
        self.last = self.shown.copy()
        return self.shown.copy(), settle(shown_speed)

    def _hold(self, shapes: tuple[TeamShape, TeamShape], pos: np.ndarray, ball: np.ndarray, k: int,
              taker: int) -> None:
        plan, shown = self.plan, self.shown
        self.held += 1
        self.released = 0
        goal = from_view(GOAL_V, k)
        target = pos.copy()
        vmax = np.full((2, 11), WALK_MS)
        for (side, i), spot in plan.spots.items():
            target[side, i] = from_view(spot, k)
        for j, i in plan.mark.items():                    # a metre goal-side of his man, wherever he goes
            man = shown[k, i]
            to_goal = goal - man
            target[1 - k, j] = man + to_goal / max(float(norm(to_goal)), 1e-6) * 1.0
            vmax[1 - k, j] = MARK_MS
        for side, i in sorted(plan.jostle):
            target[side, i] = target[side, i] + normal(self.rng, 0.0, 0.25, 2)
        target[k, taker] = pos[k, taker]
        vmax[k, taker] = CHASE_MS
        vmax = np.minimum(vmax, self.top)
        step = target - shown
        dist = norm(step)
        scale = np.minimum(1.0, vmax / np.maximum(dist, 1e-9))
        new = shown + step * scale[..., None]
        # Nobody of the other side within 9.15 m once they have had time to get back.
        if self.held > 3:
            away = new[1 - k] - ball
            d = norm(away)
            near = d < KEEP_OFF + 0.05
            if near.any():
                push = np.where(d > 1e-6, (KEEP_OFF + 0.1) / np.maximum(d, 1e-6), 1.0)
                new[1 - k] = np.where(near[:, None], ball + away * push[:, None], new[1 - k])
        new = np.clip(new, [0.3, 0.3], [PITCH_LENGTH - 0.3, PITCH_WIDTH - 0.3])
        active = np.stack([shapes[0].active, shapes[1].active])
        self.shown = settle(np.where(active[..., None], new, pos))

    def _release(self, t: int, pos: np.ndarray, speed: np.ndarray, ball: np.ndarray,
                 owner: tuple[int, int] | None, flight: dict | None) -> None:
        """After the kick. Whoever the ball comes to (the man on it at once, the one a pass is played
        to as it arrives, anyone the engine has near it) goes to where the engine has him; the rest
        hold their spots while the ball is still around the box, as defenders do until it is
        cleared, then everybody runs back to where the engine has them."""
        self.released += 1
        shown = self.shown
        step = pos - shown
        dist = norm(step)
        self.involved |= norm(pos - ball) < INVOLVED_M
        if owner is not None:
            self.involved[owner] = True
        if flight is not None and flight.get("team") is not None:
            self.involved[flight["team"], flight["slot"]] = True
        if owner is not None and owner[0] != self.after:
            self.won = True                               # the defending side has it: the box empties
        near_goal = float(to_view(ball, self.after)[0]) > PITCH_LENGTH - STAY_M
        staying = self.released <= STAY_S and near_goal and not self.won
        # catching up with a man who is running himself takes a little more than his own speed
        run = np.minimum(np.maximum(RUN_MS, speed + 1.0), CHASE_MS)
        vmax = np.where(self.involved, CHASE_MS, 0.0 if staying else run)
        if flight is not None and flight.get("team") is not None:
            k, i = flight["team"], flight["slot"]
            vmax[k, i] = max(float(dist[k, i]) / max(flight["arrive"] - t, 1), RUN_MS)
        vmax = np.minimum(vmax, self.top)
        scale = np.minimum(1.0, vmax / np.maximum(dist, 1e-9))
        new = shown + step * scale[..., None]
        close = (norm(pos - new) < 0.5) & (norm(pos - shown) <= self.top)
        new = np.where(close[..., None], pos, new)                          # close enough: he is there
        self.shown = settle(new)
        if self.released >= RELEASE_S:
            self.shown = None
