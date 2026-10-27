"""The match centre on the home page (C14, #354): the match played as live, and every stored match.

GET /api/hub

- `live`: one simulated match whose clock is tied to the wall clock, so every visit lands in the
  middle of it and every viewer sees the same minute. Its elapsed time is
  (now - LIVE_ANCHOR) mod (its length + LIVE_BREAK_S); after the final whistle and a short break
  it kicks off again. The page replays the stored match up to that second (data/live/replay.tsx);
  nothing is simulated on the server. `PIVOT_LIVE_MATCH` picks the match, else the second listed
  (the first is the one the site has always opened, the demo video's).
- `next`: the next round's fixtures (nextround.py), each with its prediction when one was worked out.
- `schedule` (C15): every round still to come, matchdays 31-38, with its date; a fixture's
  prediction is there only when its round was worked out ahead of time.
- `matches`: every stored match in the /api/matches order, with its matchday, score, how many
  turning points it has and its best-rated player. The live one is in the list, marked.
- `history` (#364): the whole league's season so far, every round in eval/fixtures/season-2026.json
  (matchdays 1-29, 290 games), latest first, each game with its score and red cards. A game links to
  its full match (`match_id`) only when one is stored under the season fixture's id
  (`S2026-07-COR-TES`, world.fixture_match); the rest are scores only.

Read-only. A finished match's line is kept in memory after the first request.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from pivot_core.domain import Match
from pivot_core.sim.world import BY_ID, SEASON

from . import nextround, sims
from .players import _cache, _stored_lines
from .prematch import matchday_of
from .routes import list_matches

router = APIRouter(prefix="/api")

LIVE_ANCHOR = datetime(2026, 10, 27, tzinfo=UTC).timestamp()
LIVE_BREAK_S = 120                     # between the final whistle and the next kick-off
MIN_MINUTES = 20                       # as bestPlayer in apps/web/src/data/persona.ts


def live_id(matches: list[Match]) -> str | None:
    asked = os.environ.get("PIVOT_LIVE_MATCH")
    ids = [m.match_id for m in matches if m.status == "finished" and m.preset is None]
    if asked in ids:
        return asked
    return ids[1] if len(ids) > 1 else ids[0] if ids else None


def live_clock(length_s: int, now: float) -> int:
    """The live match's elapsed second at `now` (unix seconds); past `length_s` is the break before the next kick-off."""
    return int((now - LIVE_ANCHOR) % (length_s + LIVE_BREAK_S))


def _team(t) -> dict:
    return {"name": t.name, "short_name": t.short_name, "color": t.color}


def _best(request: Request, match: Match) -> dict | None:
    names = {p.player_id: (p.name, p.team) for t in (match.home, match.away) for p in t.squad}
    lines = [s for s in _stored_lines(request, match.match_id) or []
             if s.get("minutes_played", 0) >= MIN_MINUTES and s.get("player_id") in names]
    if not lines:
        return None
    top = max(lines, key=lambda s: s["rating"])
    name, team = names[top["player_id"]]
    return {"player_id": top["player_id"], "name": name, "team": team, "rating": round(top["rating"], 1)}


async def _line(request: Request, match: Match) -> dict:
    cache = _cache(request, "hub_lines")
    if match.status == "finished" and match.match_id in cache:
        return cache[match.match_id]
    pivots = await request.app.state.adapters.matches.list_pivots(match.match_id)
    line = {
        "match_id": match.match_id, "matchday": matchday_of(match), "status": match.status,
        "home": _team(match.home), "away": _team(match.away), "score": match.score.model_dump(),
        "length_s": match.clock, "periods": [p.model_dump() for p in match.periods],
        "pivots": sum(p.status in ("confirmed", "degraded") for p in pivots),
        "best": _best(request, match),
    }
    if match.status == "finished":
        cache[match.match_id] = line
    return line


def _club(club_id: str) -> dict:
    c = BY_ID[club_id]
    return {"name": c.name, "short_name": c.short, "color": c.color}


def history(stored: set[str]) -> list[dict]:
    """The season's played rounds, latest first: each game's clubs, score and red cards."""
    season = sims._season()
    if season is None:
        return []
    rounds: dict[int, list[dict]] = {}
    for r in season["results"]:
        if r["season"] != SEASON or r["home"] not in BY_ID or r["away"] not in BY_ID:
            continue
        md = r["matchday"]
        fid = f"S{r['season']}-{md:02d}-{BY_ID[r['home']].short}-{BY_ID[r['away']].short}"
        reds = [x[0] if isinstance(x, list) else x.get("team") for x in r.get("reds", [])]
        rounds.setdefault(md, []).append({
            "home": _club(r["home"]), "away": _club(r["away"]),
            "score": {"home": r["score"][0], "away": r["score"][1]},
            "reds": {"home": reds.count(r["home"]), "away": reds.count(r["away"])},
            "match_id": fid if fid in stored else None,
        })
    return [{"matchday": md, "date": nextround.round_date(md).isoformat(), "results": rounds[md]}
            for md in sorted(rounds, reverse=True)]


@router.get("/hub")
async def hub(request: Request) -> dict:
    """The live match (its wall-clock second, goal and pivot times) and a line for every stored match."""
    matches = await list_matches(request)
    lines = [await _line(request, m) for m in matches]
    live = live_id(matches)
    status = getattr(request.app.state, "sims", None)
    nxt = getattr(request.app.state, "next_round", None)
    by_id = {m.match_id: m for i in (nxt["order"] if nxt else [])
             if (m := await request.app.state.adapters.matches.get_match(i)) is not None}
    out = {"matches": [{**line, "live": line["match_id"] == live} for line in lines], "live": None,
           "generating": bool(status and status.as_dict()["generating"]), "next": None, "schedule": [],
           "history": history({m.match_id for m in matches if m.status == "finished"})}
    if nxt:
        def fixture(i: str) -> dict:
            return {"match_id": i, "home": _team(by_id[i].home), "away": _team(by_id[i].away),
                    "venue": by_id[i].context.venue, "prediction": nxt["predictions"].get(i)}

        rounds = [{"matchday": r["matchday"], "date": r["date"], "fixtures": [fixture(i) for i in r["ids"] if i in by_id]}
                  for r in nxt["rounds"]]
        out["next"] = rounds[0] if rounds else None
        out["schedule"] = rounds
    if live is not None:
        match = next(m for m in matches if m.match_id == live)
        events = await request.app.state.adapters.matches.list_events(live)
        pivots = await request.app.state.adapters.matches.list_pivots(live)
        out["live"] = {
            "match_id": live, "anchor": LIVE_ANCHOR, "break_s": LIVE_BREAK_S, "length_s": match.clock,
            "clock": live_clock(match.clock, time.time()), "periods": [p.model_dump() for p in match.periods],
            "goals": [{"t": e.t, "team": e.team} for e in events if e.type == "shot" and e.shot_outcome == "goal"],
            "pivot_minutes": sorted(p.minute for p in pivots if p.status in ("confirmed", "degraded")),
        }
    return out
