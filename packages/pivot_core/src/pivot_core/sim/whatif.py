"""What-if: save a match at a minute and play it on many times, as it was and with one change (B04, B08).

How a scenario is run (ADR-0009):

1. `save` plays the match with its own seed and plants up to `spec.at_minute` (elapsed, t // 60)
   and keeps the engine there. Everything before that minute is the match that was played.
2. `prepare` makes two starting points from the save: the baseline keeps everything as it was,
   the counterfactual gets the change (`_apply`, one rule per scenario type below).
3. Run i of both arms copies its starting point, reseeds it with `seed_base + i` and plays to
   full time (`play_on`). Paired seeds: the two arms differ only by the change.
4. `summarise` counts wins, draws and losses per arm with Wilson 95 % intervals.

A new seed does not repeat what happened after the save, so an event a scenario takes away
must be put back into the baseline by hand. Planted events (the demo's 38' red card and 63'
change) are already forced in both arms; an event the simulation produced on its own is
planted into the baseline only. The counterfactual then leaves it out:

- remove_red_card: the card is not given; the player stays on. Other cards can still come.
- cancel_substitution: the change is not made, and automatic substitutions leave both players
  alone for the rest of the match. A planted change is cancelled whole, with the tactics that
  came with it (the demo's 63' change is "h15 for h09 and drop deep").
- move_substitution: the same change (with its tactics) at `params["new_minute"]`, read on the
  match clock as the catalog does (74 = 75').
- remove_goal: saved just after the goal instead; the goal is taken off the score and the
  defending keeper restarts with a goal kick, as if it had been ruled out.
- change_press, change_tactics, change_formation: applied at the saved minute, and later
  planted changes of that team no longer touch what the scenario set (press; every tactic;
  the formation). A coach's own reaction to a red card still reshapes the team.
- change_lineup: the players in `team_sheet` who are not on the pitch come on for those who are
  not in it, at the next stoppage (at most five substitutions in all).

Runs go through a process pool. On Windows the pool starts fresh interpreters, so a script that
calls `run_whatif` must guard its entry point with `if __name__ == "__main__":`.
"""

from __future__ import annotations

import copy
import hashlib
import math
import os
import pickle
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor, as_completed

import numpy as np

from ..domain import Match, OutcomeDist, PlantSpec, ScenarioSpec, SimResult
from ..domain.common import PERIOD_BASE_MINUTE, PERIOD_LENGTH_MINUTES, PITCH_WIDTH
from .engine import SIDES, Engine, Params
from .formations import FORMATIONS
from .movement import from_view

TACTIC_KEYS = ("line_height", "press", "width", "tempo", "passing", "attack_focus")
SUB_KEYS = ("player_off", "player_on", "reason")
OUTCOMES = ("home_win", "draw", "away_win")
MAX_SUBS = 5
MOVE_RANGE = (46, 85)                 # clock minutes a moved substitution may land on (D07 catalog)
CHUNK = 10                            # runs per pool task: small enough for a smooth progress bar
Z95 = 1.959963984540054

Score = tuple[int, int]
Progress = Callable[[int, int], None]     # (runs finished, runs in total)


# --- save and play on (B04) ------------------------------------------------------------

def save(match: Match, minute: int, seed: int | None = None, plants: Iterable[PlantSpec] = (),
         params: Params | None = None) -> Engine:
    """The match played with its own seed and plants up to elapsed `minute`, ready to play on."""
    eng = Engine(match, seed, params, list(plants))
    eng.record_frames = False
    eng.play(until_t=minute * 60)
    return eng


def copy_engine(eng: Engine) -> Engine:
    """A copy that can be played on without touching `eng`. The squads never change during a
    match, so they are shared instead of copied."""
    shared = (eng.match, eng.teams, eng.players, eng.attr, eng.p)
    return copy.deepcopy(eng, {id(x): x for x in shared})


def play_on(saved: Engine, seed: int | None = None) -> Engine:
    """A copy of `saved` played to full time. With a seed it is reseeded first; without one it
    plays on exactly as the original match did."""
    eng = copy_engine(saved)
    if seed is not None:
        eng.reseed(seed)
    eng.play()
    return eng


# --- scenarios -------------------------------------------------------------------------

def clock_minute(period: int, period_t: int) -> int:
    """Scoreboard minute, as plants use it: 63 for 63', 45 in first-half added time."""
    base, length = PERIOD_BASE_MINUTE[period], PERIOD_LENGTH_MINUTES[period]
    return base + min(period_t // 60 + 1, length)


def find_event(saved: Engine, event_id: str) -> tuple[Engine, dict]:
    """Play a copy of the save on, one second at a time, until `event_id` happens.

    Returns the copy (stopped just after the event) and the event. With its original seed the
    copy replays the real match, so the event comes out exactly as it was.
    """
    if any(e["event_id"] == event_id for e in saved.events):
        raise ValueError(f"{event_id} happened before the saved minute; resume from an earlier minute")
    probe = copy_engine(saved)
    seen = len(probe.events)
    while True:
        over = probe.play(until_t=probe.t + 1)
        for e in probe.events[seen:]:
            if e["event_id"] == event_id:
                return probe, e
        seen = len(probe.events)
        if over:
            raise ValueError(f"{event_id} is not an event of this match")


def _side(spec: ScenarioSpec, target: dict | None) -> int:
    team = spec.team or (target or {}).get("team")
    if team not in SIDES:
        raise ValueError(f"{spec.type} needs a team")
    return SIDES.index(team)


def _plant(eng: Engine, spec: PlantSpec) -> None:
    eng.plants.append({"spec": spec, "done": False})


def _strip(eng: Engine, k: int, keys: Iterable[str], players: set[str] | None = None) -> None:
    """Take `keys` out of team k's plants still to come. With `players`, only plants that
    involve one of them lose the keys (a substitution of a player who is already off)."""
    keys = set(keys)
    for plant in eng.plants:
        spec = plant["spec"]
        if plant["done"] or spec.team != SIDES[k]:
            continue
        if players is not None and not players & {str(spec.params.get(key)) for key in ("player_off", "player_on")}:
            continue
        params = {key: v for key, v in spec.params.items() if key not in keys}
        type_ = "press_change" if spec.type == "substitution" and "player_off" in keys else spec.type
        plant["spec"] = spec.model_copy(update={"params": params, "type": type_})


def _sub_plant(team: str, minute: int, sub: dict, extra: dict | None = None) -> PlantSpec:
    params = {"player_off": sub["player_off_id"], "player_on": sub["player_on_id"], "reason": sub["reason"]}
    return PlantSpec(minute=minute, type="substitution", team=team, params={**params, **(extra or {})})


def _expect(target: dict | None, what: str, ok: bool) -> dict:
    if target is None or not ok:
        raise ValueError(f"the target event is not {what}")
    return target


def _apply(base: Engine, cf: Engine, spec: ScenarioSpec, target: dict | None) -> None:
    """Make the counterfactual differ from the baseline by exactly the scenario's change."""
    k = _side(spec, target)
    planted = target.get("_plant") if target else None
    if spec.type == "remove_red_card":
        _expect(target, "a red card", target is not None and target["type"] == "card"
                and target["foul"]["card"] in ("red", "second_yellow"))
        if planted is None:
            _plant(base, PlantSpec(minute=clock_minute(target["period"], target["period_t"]), type="red_card",
                                   team=target["team"], params={"player_id": target["player_id"],
                                                                "reason": target["foul"]["card_reason"]}))
        else:
            cf.plants[planted]["done"] = True
    elif spec.type in ("cancel_substitution", "move_substitution"):
        sub = _expect(target, "a substitution", target is not None and target["type"] == "substitution")["substitution"]
        minute = clock_minute(target["period"], target["period_t"])
        if planted is None:
            _plant(base, _sub_plant(target["team"], minute, sub))
            moved = _sub_plant(target["team"], minute, sub)
        else:
            cf.plants[planted]["done"] = True
            moved = cf.plants[planted]["spec"]
        if spec.type == "cancel_substitution":
            cf.kept |= {sub["player_off_id"], sub["player_on_id"]}
            return
        new = int(spec.params.get("new_minute", -1))      # elapsed minute on the catalog's clock
        if not MOVE_RANGE[0] <= new + 1 <= MOVE_RANGE[1] or new < spec.at_minute:
            raise ValueError(f"new_minute {new} must be {MOVE_RANGE[0] - 1}-{MOVE_RANGE[1] - 1} and not before "
                             f"at_minute {spec.at_minute}")
        _plant(cf, moved.model_copy(update={"minute": new + 1}))
    elif spec.type == "remove_goal":
        _expect(target, "a goal", target is not None and target["type"] == "shot" and target["shot_outcome"] == "goal")
        k = SIDES.index(target["team"])
        cf.score[k] -= 1
        cf.half_counts["goals"] = max(cf.half_counts["goals"] - 1, 0)
        r = cf.restart
        if r is not None and r["kind"] == "kick_off" and not r["period_start"]:
            opp = 1 - k
            cf._set_restart("goal_kick", opp, from_view(np.array([5.5, PITCH_WIDTH / 2]), opp), wait=max(cf.dead, 1))
        next(e for e in cf.events if e["event_id"] == target["event_id"])["_disallowed"] = True
    elif spec.type in ("change_press", "change_tactics"):
        if spec.tactics is None:
            raise ValueError(f"{spec.type} needs tactics")
        if spec.type == "change_press":
            keys: tuple[str, ...] = ("press",)
        else:
            keys = TACTIC_KEYS
            cf.tactics[k] = spec.tactics            # the fields _change_tactics does not copy, too
        cf._change_tactics(k, spec.tactics.model_dump(include=set(keys)))
        _strip(cf, k, keys)
    elif spec.type == "change_formation":
        formation = spec.team_sheet.formation if spec.team_sheet else str(spec.params.get("formation", ""))
        if formation not in FORMATIONS:
            raise ValueError(f"unknown formation {formation!r}; known: {sorted(FORMATIONS)}")
        cf._change_tactics(k, {"formation": formation})
        _strip(cf, k, ("formation",))
    elif spec.type == "change_lineup":
        if spec.team_sheet is None:
            raise ValueError("change_lineup needs a team_sheet")
        on_pitch = {p for p in cf.shapes[k].player_ids if p}
        now = {s.player_id: s.slot for s in cf.sheets[k].starters if s.player_id in on_pitch}
        want = {s.player_id: s.slot for s in spec.team_sheet.starters}
        outs = sorted((p for p in now if p not in want), key=now.get)
        ins = sorted((p for p in want if p not in now), key=want.get)
        bad = [p for p in ins if p not in cf.sheets[k].bench]
        if bad or len(ins) != len(outs) or not ins:
            raise ValueError(f"change_lineup must swap players on the pitch for players on the bench "
                             f"(coming on {ins}, going off {outs}, not on the bench {bad})")
        if cf.subs_used[k] + len(ins) > MAX_SUBS:
            raise ValueError(f"{len(ins)} substitutions on top of {cf.subs_used[k]} is more than {MAX_SUBS}")
        _strip(cf, k, SUB_KEYS, players=set(ins) | set(outs))
        minute = clock_minute(cf.period, cf.t - cf.period_start)
        for off, on in zip(outs, ins):
            _plant(cf, PlantSpec(minute=minute, type="substitution", team=SIDES[k],
                                 params={"player_off": off, "player_on": on, "reason": "tactical"}))
    else:
        raise ValueError(f"unknown scenario type {spec.type}")


NEEDS_TARGET = ("remove_red_card", "cancel_substitution", "move_substitution", "remove_goal")


def prepare(saved: Engine, spec: ScenarioSpec) -> tuple[Engine, Engine]:
    """Baseline and counterfactual starting points for a scenario from a save at `spec.at_minute`."""
    target = None
    if spec.type in NEEDS_TARGET:
        if not spec.target_event_id:
            raise ValueError(f"{spec.type} needs target_event_id")
        probe, target = find_event(saved, spec.target_event_id)
        if spec.type == "remove_goal":
            saved = probe                       # the goal is part of the history both arms share
    base, cf = copy_engine(saved), copy_engine(saved)
    _apply(base, cf, spec, target)
    return base, cf


# --- batch (B08) -----------------------------------------------------------------------

_STARTS: dict[str, Engine] = {}           # per worker process: starting points already unpickled


def run_shard(key: str, blob: bytes, seeds: list[int]) -> list[Score]:
    """Final scores of the runs `seeds` from a pickled starting point (one pool task; ADR-0009)."""
    start = _STARTS.get(key)
    if start is None:
        if len(_STARTS) >= 4:
            _STARTS.pop(next(iter(_STARTS)))
        start = _STARTS[key] = pickle.loads(blob)
    return [_score(play_on(start, s)) for s in seeds]


def _score(eng: Engine) -> Score:
    return int(eng.score[0]), int(eng.score[1])


def run_arms(starts: Sequence[Engine], n_runs: int, seed_base: int, workers: int | None = None,
             progress: Progress | None = None, pool: Executor | None = None) -> list[list[Score]]:
    """Final scores of `n_runs` runs from each starting point; run i uses `seed_base + i` in every arm.

    `workers` <= 1 with no `pool` runs in this process. A long-lived `pool` can be passed in to
    skip the start-up of a new one. The scores do not depend on how the runs are spread.
    """
    seeds = list(range(seed_base, seed_base + n_runs))
    total = len(starts) * n_runs
    results: list[list[Score]] = [[(0, 0)] * n_runs for _ in starts]
    done = 0
    workers = workers or os.cpu_count() or 1
    if pool is None and workers <= 1:
        for i, s in enumerate(seeds):
            for a, start in enumerate(starts):
                results[a][i] = _score(play_on(start, s))
                done += 1
                if progress:
                    progress(done, total)
        return results
    blobs = [pickle.dumps(s, protocol=pickle.HIGHEST_PROTOCOL) for s in starts]
    keys = [hashlib.sha1(b).hexdigest() for b in blobs]
    ex = pool or ProcessPoolExecutor(max_workers=min(workers, math.ceil(total / CHUNK)))
    try:
        futures = {ex.submit(run_shard, keys[a], blobs[a], seeds[lo:lo + CHUNK]): (a, lo)
                   for lo in range(0, n_runs, CHUNK) for a in range(len(starts))}
        for f in as_completed(futures):
            a, lo = futures[f]
            chunk = f.result()
            results[a][lo:lo + len(chunk)] = chunk
            done += len(chunk)
            if progress:
                progress(done, total)
    finally:
        if pool is None:
            ex.shutdown(cancel_futures=True)
    return results


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes in n runs (95 % by default)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def summarise(scores: Sequence[Score]) -> OutcomeDist:
    n = len(scores)
    counts = {"home_win": sum(h > a for h, a in scores), "draw": sum(h == a for h, a in scores),
              "away_win": sum(h < a for h, a in scores)}
    return OutcomeDist(**{key: c / n for key, c in counts.items()}, ci95={key: wilson(c, n) for key, c in counts.items()})


def significant(a: OutcomeDist, b: OutcomeDist) -> dict[str, bool]:
    """True for an outcome only when the two arms' intervals do not overlap."""
    out = {}
    for key in OUTCOMES:
        (lo1, hi1), (lo2, hi2) = a.ci95[key], b.ci95[key]
        out[key] = hi1 < lo2 or hi2 < lo1
    return out


def run_whatif(match: Match, spec: ScenarioSpec, *, seed: int | None = None, plants: Iterable[PlantSpec] = (),
               params: Params | None = None, workers: int | None = None, progress: Progress | None = None,
               pool: Executor | None = None, scenario_id: str | None = None, n_runs: int | None = None) -> SimResult:
    """Run a scenario: baseline and counterfactual, `spec.n_runs` each (`n_runs` overrides it).

    `match`, `seed` and `plants` must be what the real match was simulated with, e.g.
    `DEMO_1021.build()` and `DEMO_1021.plants`. `progress(done, total)` is called as runs finish.
    """
    t0 = time.perf_counter()
    base, cf = prepare(save(match, spec.at_minute, seed, plants, params), spec)
    runs = n_runs or spec.n_runs
    scores = run_arms([base, cf], runs, spec.seed_base, workers, progress, pool)
    b, c = summarise(scores[0]), summarise(scores[1])
    return SimResult(scenario_id=scenario_id or f"{match.match_id}:{spec.pivot_id}:{spec.type}", baseline=b,
                     counterfactual=c, significant=significant(b, c),
                     runtime_ms=int((time.perf_counter() - t0) * 1000), executor="local_pool")


__all__ = ["clock_minute", "copy_engine", "find_event", "play_on", "prepare", "run_arms", "run_shard", "run_whatif",
           "save", "significant", "summarise", "wilson"]
