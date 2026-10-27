"""The match centre on the home page (C14, #354): the match played as live, and every stored match.

GET /api/hub

- `live`: one simulated match whose clock is tied to the wall clock, so every visit lands in the
  middle of it and every viewer sees the same minute. Its elapsed time is
  (now - LIVE_ANCHOR) mod (its length + LIVE_BREAK_S); after the final whistle and a short break
  it kicks off again. The page replays the stored match up to that second (data/live/replay.tsx);
  nothing is simulated on the server. `PIVOT_LIVE_MATCH` picks the match, else the second listed
  (the first is the one the site has always opened, the demo video's).
- `next`: the next round's fixtures (nextround.py), each with its prediction when one was worked out.
- `matches`: every stored match in the /api/matches order, with its matchday, score, how many
  turning points it has and its best-rated player. The live one is in the list, marked.

Read-only. A finished match's line is kept in memory after the first request.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from pivot_core.domain import Match

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
           "generating": bool(status and status.as_dict()["generating"]), "next": None}
    if nxt:
        out["next"] = {"matchday": nxt["matchday"], "fixtures": [
            {"match_id": i, "home": _team(by_id[i].home), "away": _team(by_id[i].away),
             "venue": by_id[i].context.venue, "prediction": nxt["predictions"].get(i)}
            for i in nxt["order"] if i in by_id]}
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
