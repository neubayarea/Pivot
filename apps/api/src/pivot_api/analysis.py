"""The analyst's post-match report (C19, #385): six ways to read one match, worked out from the same
StatCalculator the AI cites and the Verifier checks.

GET /api/matches/{id}/analysis[?up_to=<seconds>]

- deserved: each shot's xG is an independent chance to score; 10,000 draws from the match's seed give
  how often each side would have won, and the expected points (Understat's xPts).
- phases: six spells of the match clock, 0-15', 15-30', 30-45+' (to the half-time whistle), 45-60',
  60-75', 75-90+' (to the end), each the calculator's window of elapsed minutes. The spells are
  contiguous, so their xG adds up to the match's. The second half's spells start at the first whole
  minute after its kick-off, so a second-half shot in that first part-minute counts in 30-45+'.
- game_state: the match cut at each goal into level, home leading and away leading. A goal counts in
  the state it was scored in. Per state: minutes played in it, xG for and against per 90, and
  possession and field tilt as the minute-weighted average of its windows (a window with no answer
  carries no weight), never a plain average of percentages.
- shot_quality: shots, xG per shot, big chances (xG >= 0.3), and xG by where the move came from
  (`play_pattern`: open play, set piece, penalty, counter).
- lanes: entries into the final third and into the box (successful passes and carries, as
  `box_entries` counts them) and shot xG, in thirds of the pitch's width seen from the attacker:
  the attacker's left is the high-y side (`pivot_core.domain.common.lane_of`). The box lies inside
  the middle third, so a box entry counts in the lane it came from, a final-third entry in the lane
  it reached, and a shot's xG in the lane of the pass that set it up (the shot's own, without one).
- profile: eight match stats as percentiles against both teams' values in every finished stored
  match (PPDA inverted: a lower PPDA, a harder press, is a higher percentile). The baseline is kept.

- rolling (C21, #401): five-minute windows of elapsed minutes from kick-off to `up_to` (or the end),
  each with the same stats as a phase, for the live panel's trend lines.
- subs (C21, #401): one row per substitution, both teams' xG and field tilt over the 15 minutes
  before it and the 15 after (elapsed minutes; the substitution's own minute counts after). A window
  stops short at kick-off, the half-time or full-time whistle, `up_to`, or another substitution's
  minute (one made in the same minute is the same change); `cut_before` / `cut_after` say which, and
  `minutes_before` / `minutes_after` are the minutes of play the window really has.

`up_to` counts only what happened by that elapsed second, for a live match or a replay. A finished
match's report is kept after the first request. A number with no answer is null, never 0.
"""

from __future__ import annotations

import asyncio
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field

from pivot_core.analytics import StatCalculator
from pivot_core.domain import Match, MatchEvent, StatRef
from pivot_core.domain.common import PITCH_WIDTH, Model, area_of, attacking_view, third_of

from . import matchdata

router = APIRouter(prefix="/api")

Side = Literal["home", "away"]
SIDES: tuple[Side, Side] = ("home", "away")
N_SIMS = 10_000
BIG_CHANCE = 0.3
PHASE_MINUTES = 15
PROFILE = ("xg", "shots", "possession_pct", "field_tilt_pct", "progressive_passes", "ppda", "line_height_m",
           "tackles_won")
INVERTED = {"ppda"}                           # lower is better: a harder press
SOURCES = {"open_play": "open_play", "kick_off": "open_play", "goal_kick": "open_play", "corner": "set_piece",
           "free_kick": "set_piece", "throw_in": "set_piece", "penalty": "penalty", "counter": "counter"}
BOX = ("opp_box", "opp_six_yard_box")


# --- the response ---------------------------------------------------------------------------------

class AnalysisDeserved(Model):
    n_sims: int
    home_win: float
    draw: float
    away_win: float
    xpts: dict[Side, float]


class AnalysisPhaseTeam(Model):
    xg: float | None
    field_tilt_pct: float | None
    possession_pct: float | None
    ppda: float | None
    shots: float | None


class AnalysisPhase(Model):
    """`from` / `to`: the spell on the match clock (45 is the second half's kick-off); `window`: the
    elapsed minutes it covers (from <= minute < to)."""
    start: int = Field(alias="from")
    end: int = Field(alias="to")
    window: tuple[int, int]
    home: AnalysisPhaseTeam
    away: AnalysisPhaseTeam


class AnalysisStateTeam(Model):
    xg_per90: float | None
    xga_per90: float | None
    possession_pct: float | None
    field_tilt_pct: float | None


class AnalysisGameState(Model):
    state: Literal["level", "home_leading", "away_leading"]
    minutes: float
    home: AnalysisStateTeam
    away: AnalysisStateTeam


class AnalysisShotQuality(Model):
    shots: int
    xg_per_shot: float | None
    big_chances: int
    by_source: dict[Literal["open_play", "set_piece", "penalty", "counter"], float]


class AnalysisLane(Model):
    final_third_entries: int
    entries: int                              # box entries
    xg: float


class AnalysisProfile(Model):
    baseline_matches: int
    metrics: list[str]
    home: list[float | None]                  # percentiles 0-100, in the order of `metrics`
    away: list[float | None]
    home_values: list[float | None]           # the match values they come from
    away_values: list[float | None]


class AnalysisRolling(Model):
    """`from` / `to`: elapsed minutes (from <= minute < to); `period`: the period the window starts in."""
    start: int = Field(alias="from")
    end: int = Field(alias="to")
    period: int
    home: AnalysisPhaseTeam
    away: AnalysisPhaseTeam


class AnalysisSubTeam(Model):
    xg: float | None
    field_tilt_pct: float | None


Cut = Literal["kick_off", "half_time", "full_time", "now", "sub"]


class AnalysisSub(Model):
    """One substitution: `minute` is the elapsed minute, `clock` the match clock's (54 for 54')."""
    event_id: str
    t: int
    minute: int
    clock: int
    period: int
    team: Side
    player_off_id: str | None
    player_off_name: str | None
    player_on_id: str | None
    player_on_name: str | None
    reason: str | None
    window_before: tuple[int, int]
    window_after: tuple[int, int]
    minutes_before: float
    minutes_after: float
    cut_before: Cut | None                    # why the window is shorter than 15 minutes, if it is
    cut_after: Cut | None
    before: dict[Side, AnalysisSubTeam]
    after: dict[Side, AnalysisSubTeam]


class MatchAnalysis(Model):
    match_id: str
    up_to_t: int
    deserved: AnalysisDeserved
    phases: list[AnalysisPhase]
    game_state: list[AnalysisGameState]
    shot_quality: dict[Side, AnalysisShotQuality]
    lanes: dict[Side, dict[Literal["left", "centre", "right"], AnalysisLane]]
    profile: AnalysisProfile
    rolling: list[AnalysisRolling]
    subs: list[AnalysisSub]


CONTRACT_MODELS = (AnalysisDeserved, AnalysisPhaseTeam, AnalysisPhase, AnalysisStateTeam, AnalysisGameState,
                   AnalysisShotQuality, AnalysisLane, AnalysisProfile, AnalysisRolling, AnalysisSubTeam, AnalysisSub,
                   MatchAnalysis)


# --- the parts --------------------------------------------------------------------------------------

def _stat(calc: StatCalculator, metric: str, team: Side, window: tuple[int, int]) -> float | None:
    if window[1] <= window[0]:
        return None
    try:
        return float(calc.compute(StatRef(metric=metric, team=team, window=window)))
    except LookupError:                       # no data for it (no frames, nothing to divide by)
        return None


def _r(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x, nd)


def seen(calc: StatCalculator, end_t: int) -> list[MatchEvent]:
    """The events by `end_t`, outside a shootout."""
    return [e for e in calc.events if e.t <= end_t and e.period != 5]


def shots_of(events: list[MatchEvent], team: Side | None = None) -> list[MatchEvent]:
    return [e for e in events if e.type == "shot" and (team is None or e.team == team)]


def deserved(shots: list[MatchEvent], seed: int) -> AnalysisDeserved:
    """Each shot scores with its xG, independently; N_SIMS draws."""
    rng = np.random.default_rng([seed, 385])
    goals = {}
    for side in SIDES:
        xg = np.array([s.xg or 0.0 for s in shots if s.team == side])
        goals[side] = (rng.random((N_SIMS, len(xg))) < xg).sum(axis=1) if len(xg) else np.zeros(N_SIMS, int)
    home, away = goals["home"], goals["away"]
    hw, dr, aw = float(np.mean(home > away)), float(np.mean(home == away)), float(np.mean(home < away))
    return AnalysisDeserved(n_sims=N_SIMS, home_win=round(hw, 4), draw=round(dr, 4), away_win=round(aw, 4),
                            xpts={"home": round(3 * hw + dr, 2), "away": round(3 * aw + dr, 2)})


def phase_windows(match: Match, end_t: int) -> list[tuple[int, int, tuple[int, int]]]:
    """(clock from, clock to, elapsed window) for the six spells of normal time, cut at `end_t`."""
    periods = {p.period: p for p in match.periods}
    last = end_t // 60 + 1
    out = []
    second = periods.get(2)
    half = (second.start_t + 59) // 60 if second and second.start_t <= end_t else last
    for i, lo in enumerate((0, 15, 30)):
        hi = half if i == 2 else min(lo + PHASE_MINUTES, half)
        out.append((lo, lo + PHASE_MINUTES, (min(lo, half), hi)))
    if second and second.start_t <= end_t:
        for i in range(3):
            lo = half + i * PHASE_MINUTES
            hi = last if i == 2 else min(lo + PHASE_MINUTES, last)
            out.append((45 + i * PHASE_MINUTES, 60 + i * PHASE_MINUTES, (min(lo, last), hi)))
    return out


def phases(calc: StatCalculator, match: Match, end_t: int) -> list[AnalysisPhase]:
    out = []
    for lo, hi, window in phase_windows(match, end_t):
        teams = {side: AnalysisPhaseTeam(**{m: _r(_stat(calc, m, side, window)) for m in
                                            ("xg", "field_tilt_pct", "possession_pct", "ppda", "shots")})
                 for side in SIDES}
        out.append(AnalysisPhase.model_validate({"from": lo, "to": hi, "window": window, **teams}))
    return out


def _state(home: int, away: int) -> str:
    return "level" if home == away else "home_leading" if home > away else "away_leading"


def state_windows(calc: StatCalculator, end_t: int) -> list[tuple[str, tuple[int, int], float]]:
    """(state, elapsed window, minutes played in it): the match cut one minute after each goal's."""
    goals = sorted((e for e in shots_of(seen(calc, end_t)) if e.shot_outcome == "goal"), key=lambda e: e.t)
    last = end_t // 60 + 1
    cuts, score, states = [0], {"home": 0, "away": 0}, [_state(0, 0)]
    for g in goals:
        score[g.team] += 1
        cuts.append(min(g.t // 60 + 1, last))
        states.append(_state(score["home"], score["away"]))
    cuts.append(last)
    played = [(p.start_t, min(p.end_t, end_t)) for p in calc.match.periods if p.period != 5 and p.start_t <= end_t]
    out = []
    for state, lo, hi in zip(states, cuts, cuts[1:]):
        if hi <= lo:
            continue
        secs = sum(max(0, min(b, hi * 60) - max(a, lo * 60)) for a, b in played)
        out.append((state, (lo, hi), secs / 60))
    return out


def _weighted(values: list[tuple[float | None, float]]) -> float | None:
    """The average of the values with an answer, each weighted by its minutes."""
    known = [(v, w) for v, w in values if v is not None and w > 0]
    total = sum(w for _, w in known)
    return round(sum(v * w for v, w in known) / total, 1) if total else None


def game_state(calc: StatCalculator, end_t: int) -> list[AnalysisGameState]:
    spans = state_windows(calc, end_t)
    out = []
    for state in ("level", "home_leading", "away_leading"):
        mine = [(w, m) for s, w, m in spans if s == state]
        minutes = sum(m for _, m in mine)
        if not mine or minutes <= 0:
            continue
        xg = {side: sum(_stat(calc, "xg", side, w) or 0.0 for w, _ in mine) for side in SIDES}
        teams = {}
        for side, other in (("home", "away"), ("away", "home")):
            teams[side] = AnalysisStateTeam(
                xg_per90=round(xg[side] / minutes * 90, 2), xga_per90=round(xg[other] / minutes * 90, 2),
                possession_pct=_weighted([(_stat(calc, "possession_pct", side, w), m) for w, m in mine]),
                field_tilt_pct=_weighted([(_stat(calc, "field_tilt_pct", side, w), m) for w, m in mine]))
        out.append(AnalysisGameState(state=state, minutes=round(minutes, 1), **teams))
    return out


def shot_quality(events: list[MatchEvent]) -> dict[Side, AnalysisShotQuality]:
    out = {}
    for side in SIDES:
        shots = shots_of(events, side)
        by = {"open_play": 0.0, "set_piece": 0.0, "penalty": 0.0, "counter": 0.0}
        for s in shots:
            by[SOURCES.get(s.play_pattern or "open_play", "open_play")] += s.xg or 0.0
        xg = sum(s.xg or 0.0 for s in shots)
        out[side] = AnalysisShotQuality(shots=len(shots), xg_per_shot=round(xg / len(shots), 3) if shots else None,
                                        big_chances=sum((s.xg or 0.0) >= BIG_CHANCE for s in shots),
                                        by_source={k: round(v, 2) for k, v in by.items()})
    return out


def lane(point: tuple[float, float], side: str) -> str:
    """Thirds of the width seen from the attacker; the attacker's left is the high-y side."""
    _, y = attacking_view(point, side)
    return "right" if y < PITCH_WIDTH / 3 else "left" if y >= 2 * PITCH_WIDTH / 3 else "centre"


def lanes(calc: StatCalculator, events: list[MatchEvent]) -> dict[Side, dict[str, AnalysisLane]]:
    counts = {side: {k: {"final_third_entries": 0, "entries": 0, "xg": 0.0} for k in ("left", "centre", "right")}
              for side in SIDES}
    for e in events:
        if e.team not in SIDES:
            continue
        if e.type in ("pass", "carry") and e.outcome == "success" and e.location and e.end_location:
            if third_of(e.location, e.team) != "final" and third_of(e.end_location, e.team) == "final":
                counts[e.team][lane(e.end_location, e.team)]["final_third_entries"] += 1
            if area_of(e.location, e.team) not in BOX and area_of(e.end_location, e.team) in BOX:
                counts[e.team][lane(e.location, e.team)]["entries"] += 1
        elif e.type == "shot" and e.location:
            kp = calc.key_pass(e)
            counts[e.team][lane(kp.location if kp and kp.location else e.location, e.team)]["xg"] += e.xg or 0.0
    return {side: {k: AnalysisLane(final_third_entries=v["final_third_entries"], entries=v["entries"],
                                   xg=round(v["xg"], 2)) for k, v in counts[side].items()} for side in SIDES}


def match_values(calc: StatCalculator, end_t: int) -> dict[Side, list[float | None]]:
    window = (0, end_t // 60 + 1)
    return {side: [_stat(calc, m, side, window) for m in PROFILE] for side in SIDES}


def percentile(value: float | None, baseline: list[float], inverted: bool) -> float | None:
    """The share of the baseline at or below `value` (at or above, for an inverted stat), 0-100."""
    if value is None or not baseline:
        return None
    hits = sum(b >= value for b in baseline) if inverted else sum(b <= value for b in baseline)
    return round(100 * hits / len(baseline), 1)


def profile(values: dict[Side, list[float | None]], baseline: tuple[int, list[list[float]]]) -> AnalysisProfile:
    n, columns = baseline
    pct = {side: [percentile(v, columns[i], m in INVERTED) for i, (m, v) in enumerate(zip(PROFILE, values[side]))]
           for side in SIDES}
    return AnalysisProfile(baseline_matches=n, metrics=list(PROFILE), home=pct["home"], away=pct["away"],
                           home_values=[_r(v) for v in values["home"]], away_values=[_r(v) for v in values["away"]])


def _stats_values(request: Request, match_id: str) -> dict[Side, list[float | None]] | None:
    """A match's PROFILE values from the team stats already worked out for it (/stats), if any."""
    rows = matchdata.shared(request, "team_stats", dict).get((match_id, None)) or []
    whole = next((r for r in rows if r.scope == "match"), None)
    if whole is None:
        return None
    return {side: [getattr(whole, side).get(m) for m in PROFILE] for side in SIDES}


async def _profile_values(request: Request, match: Match) -> dict[Side, list[float | None]]:
    """A match's PROFILE values, worked out once and kept as numbers (#423): from its /stats when that
    was asked, else from a calculator built for this and dropped, its frames read without being kept."""
    kept = matchdata.shared(request, "analysis_profile_values", dict)
    if match.match_id not in kept:
        values = _stats_values(request, match.match_id)
        if values is None:
            events, frames = await matchdata.inputs(request, match, keep=False)
            end = matchdata.last_second(match, events, frames)

            def work() -> dict[Side, list[float | None]]:
                return match_values(StatCalculator(match, events, frames), end)
            values = await asyncio.to_thread(work)
            del events, frames
        kept[match.match_id] = values
    return kept[match.match_id]


async def baseline(request: Request) -> tuple[int, list[list[float]]]:
    """Both teams' PROFILE values in every finished stored match: (matches, one list per metric).
    Only the numbers are kept, a few per match: no match's events, frames or calculator stay alive
    for it (#423)."""
    cache = matchdata.shared(request, "analysis_baseline", dict)
    stored = [m for m in await request.app.state.adapters.matches.list_matches() if m.status == "finished"]
    key = tuple(sorted(m.match_id for m in stored))
    if key not in cache:
        columns: list[list[float]] = [[] for _ in PROFILE]
        for m in stored:
            values = await _profile_values(request, m)
            for side in SIDES:
                for i, v in enumerate(values[side]):
                    if v is not None:
                        columns[i].append(v)
        cache.clear()
        cache[key] = (len(stored), columns)
    return cache[key]


ROLLING_MINUTES = 5
SUB_MINUTES = 15
PHASE_STATS = ("xg", "field_tilt_pct", "possession_pct", "ppda", "shots")


def _played(match: Match, end_t: int) -> list[tuple[int, int, int]]:
    """(period, first elapsed minute, end minute) of each period of play by `end_t`, back to back: a
    period after the first starts at the first whole minute after its kick-off, as the phases do."""
    periods = sorted((p for p in match.periods if p.period != 5 and p.start_t <= end_t), key=lambda p: p.start_t)
    last = end_t // 60 + 1
    starts = [0 if i == 0 else (p.start_t + 59) // 60 for i, p in enumerate(periods)]
    return [(p.period, lo, min(starts[i + 1] if i + 1 < len(periods) else last, last))
            for i, (p, lo) in enumerate(zip(periods, starts))]


def _minutes(match: Match, end_t: int, window: tuple[int, int]) -> float:
    """Minutes of play inside an elapsed-minute window."""
    spans = [(p.start_t, min(p.end_t, end_t)) for p in match.periods if p.period != 5 and p.start_t <= end_t]
    return round(sum(max(0, min(b, window[1] * 60) - max(a, window[0] * 60)) for a, b in spans) / 60, 1)


def rolling(calc: StatCalculator, match: Match, end_t: int) -> list[AnalysisRolling]:
    out = []
    played = _played(match, end_t)
    last = end_t // 60 + 1
    for lo in range(0, last, ROLLING_MINUTES):
        window = (lo, min(lo + ROLLING_MINUTES, last))
        period = next((p for p, a, b in played if a <= lo < b), played[-1][0] if played else 1)
        teams = {side: AnalysisPhaseTeam(**{m: _r(_stat(calc, m, side, window)) for m in PHASE_STATS})
                 for side in SIDES}
        out.append(AnalysisRolling.model_validate({"from": window[0], "to": window[1], "period": period, **teams}))
    return out


def _clock(e: MatchEvent) -> int:
    """The match clock's minute of an event: 54 for 54' (the second half starts at 45')."""
    return {1: 0, 2: 45, 3: 90, 4: 105}.get(e.period, 0) + e.period_t // 60 + 1


def _sub_team(calc: StatCalculator, window: tuple[int, int]) -> dict[Side, AnalysisSubTeam]:
    return {side: AnalysisSubTeam(xg=_r(_stat(calc, "xg", side, window)),
                                  field_tilt_pct=_r(_stat(calc, "field_tilt_pct", side, window))) for side in SIDES}


def subs(calc: StatCalculator, match: Match, events: list[MatchEvent], end_t: int) -> list[AnalysisSub]:
    names = {p.player_id: p.name for t in (match.home, match.away) for p in t.squad}
    played = _played(match, end_t)
    last = end_t // 60 + 1
    over = match.status == "finished" and end_t >= max((p.end_t for p in match.periods), default=0)
    changes = [e for e in events if e.type == "substitution" and e.team in SIDES]
    minutes = sorted({e.t // 60 for e in changes})
    out = []
    for e in changes:
        m = e.t // 60
        period, start, stop = next(((p, a, b) for p, a, b in played if a <= m < b), (e.period, 0, last))
        final = bool(played) and period == played[-1][0]
        prev = max((x for x in minutes if x < m), default=None)
        nxt = min((x for x in minutes if x > m), default=None)
        lo, cut_before = m - SUB_MINUTES, None
        if prev is not None and prev > lo:
            lo, cut_before = prev, "sub"
        if start > lo:
            lo, cut_before = start, "kick_off" if period == 1 else "half_time"
        hi, cut_after = m + SUB_MINUTES, None
        if nxt is not None and nxt < hi:
            hi, cut_after = nxt, "sub"
        if stop < hi:
            hi, cut_after = stop, "half_time" if not final else "full_time" if over else "now"
        before, after = (max(lo, 0), m), (m, max(hi, m))
        sub = e.substitution
        off = sub.player_off_id if sub else None
        on = sub.player_on_id if sub else e.player_id
        out.append(AnalysisSub(
            event_id=e.event_id, t=e.t, minute=m, clock=_clock(e), period=e.period, team=e.team,
            player_off_id=off, player_off_name=names.get(off or ""), player_on_id=on,
            player_on_name=names.get(on or ""), reason=getattr(sub, "reason", None),
            window_before=before, window_after=after,
            minutes_before=_minutes(match, end_t, before), minutes_after=_minutes(match, end_t, after),
            cut_before=cut_before, cut_after=cut_after,
            before=_sub_team(calc, before), after=_sub_team(calc, after)))
    return out


def analysis(calc: StatCalculator, match: Match, end_t: int, base: tuple[int, list[list[float]]]) -> MatchAnalysis:
    events = seen(calc, end_t)
    return MatchAnalysis(match_id=match.match_id, up_to_t=end_t, deserved=deserved(shots_of(events), match.seed or 0),
                         phases=phases(calc, match, end_t), game_state=game_state(calc, end_t),
                         shot_quality=shot_quality(events), lanes=lanes(calc, events),
                         profile=profile(match_values(calc, end_t), base),
                         rolling=rolling(calc, match, end_t), subs=subs(calc, match, events, end_t))


@router.get("/matches/{match_id}/analysis", response_model=MatchAnalysis)
async def get_analysis(request: Request, match_id: str, up_to: int | None = Query(None, ge=0)) -> MatchAnalysis:
    """The analyst's report on the match, up to `up_to` elapsed seconds (default: everything so far)."""
    match = await request.app.state.adapters.matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    events, frames = await matchdata.inputs(request, match)
    last = matchdata.last_second(match, events, frames)
    cut = None if up_to is None or up_to >= last else up_to

    async def work() -> MatchAnalysis:
        calc = await matchdata.calculator(request, match, cut)
        base = await baseline(request)
        return await asyncio.to_thread(analysis, calc, match, last if cut is None else cut, base)

    if match.status != "finished":
        return await work()
    if cut is not None:
        return await matchdata.cut_answer(request, "analysis", (match_id, cut), work)
    cache = matchdata.shared(request, "analysis", dict)
    if match_id not in cache:
        cache[match_id] = await work()
    return cache[match_id]


__all__ = ["CONTRACT_MODELS", "MatchAnalysis", "analysis", "deserved", "phase_windows", "router"]
