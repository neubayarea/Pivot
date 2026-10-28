"""#423: only the last few matches keep their events, frames and calculators in memory, and the
analysis baseline keeps numbers, never a match's frames."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from pivot_api import analysis, matchdata, sims
from pivot_core.domain import Match, MatchEvent

RAW = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))
MATCH = Match.model_validate(RAW["match"])
EVENTS = [MatchEvent.model_validate(e) for e in RAW["events"]]
IDS = [f"S2026-{i:02d}-AAA-BBB" for i in range(1, 6)]
MATCHES = {i: MATCH.model_copy(update={"match_id": i}) for i in IDS}


class Repo:
    async def get_match(self, mid):
        return MATCHES.get(mid)

    async def list_events(self, mid):
        return [e.model_copy(update={"match_id": mid}) for e in EVENTS]

    async def list_matches(self):
        return list(MATCHES.values())


def request():
    state = SimpleNamespace(adapters=SimpleNamespace(matches=Repo()), fixture_frames={}, sims_dir=sims.FIXTURES)
    return SimpleNamespace(app=SimpleNamespace(state=state))


def test_only_the_last_matches_asked_keep_their_inputs_and_calculators(monkeypatch):
    monkeypatch.setattr(matchdata, "MATCH_CACHE", 2)
    req = request()

    async def ask(mid):
        await matchdata.inputs(req, MATCHES[mid])
        await matchdata.calculator(req, MATCHES[mid])

    for mid in IDS[:3]:
        asyncio.run(ask(mid))
    assert list(req.app.state.match_inputs) == IDS[1:3]
    assert list(req.app.state.match_calcs) == IDS[1:3]          # the first match's calculator went with it
    asyncio.run(ask(IDS[1]))                                    # asked again: now the newest
    asyncio.run(ask(IDS[3]))
    assert list(req.app.state.match_inputs) == [IDS[1], IDS[3]]
    assert list(req.app.state.match_calcs) == [IDS[1], IDS[3]]


def test_a_read_that_does_not_keep_leaves_the_cache_alone(monkeypatch):
    monkeypatch.setattr(matchdata, "MATCH_CACHE", 2)
    req = request()
    asyncio.run(matchdata.inputs(req, MATCHES[IDS[0]]))
    events, _ = asyncio.run(matchdata.inputs(req, MATCHES[IDS[1]], keep=False))
    assert events and list(req.app.state.match_inputs) == [IDS[0]]


def test_the_baseline_keeps_numbers_only(monkeypatch):
    monkeypatch.setattr(matchdata, "MATCH_CACHE", 2)
    req = request()
    n, columns = asyncio.run(analysis.baseline(req))
    assert n == len(IDS) and len(columns) == len(analysis.PROFILE)
    assert all(len(c) <= 2 * len(IDS) for c in columns) and any(columns)
    # every match read once for it, none kept: no events, frames or calculators stay in memory
    assert not getattr(req.app.state, "match_inputs", None) and not getattr(req.app.state, "match_calcs", None)
    kept = req.app.state.analysis_profile_values
    assert set(kept) == set(IDS)
    assert all(isinstance(v, (float, int)) or v is None for vals in kept.values() for side in vals.values() for v in side)
