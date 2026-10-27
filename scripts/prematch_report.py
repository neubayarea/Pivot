#!/usr/bin/env python3
"""What pre-match context each simulated match of the site gets (Bx13).

  uv run scripts/prematch_report.py              # the 20 matches the site builds
  uv run scripts/prematch_report.py --count 6

One line per match: the round it is set on, the stakes, both sides' table place, points and last
five, head-to-head, how many news items, ties across the two squads (and within one), and context
effects (with the story ones: former club, bad blood, off-field news). Nothing is simulated: the
context comes from the season file and the squads, not from how the match is played.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from pivot_api.sims import FIXTURE, specs_first
from pivot_core.sim import build_demo_match
from pivot_core.sim.season import load_season, site_matchday, with_prematch

STORY = {"former_club", "rivalry", "off_field"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20)
    args = ap.parse_args()
    season = load_season(FIXTURE.parent)
    for spec in specs_first(args.count):
        m = with_prematch(build_demo_match(spec.seed, spec.home_strength, spec.away_strength, spec.home_formation,
                                           spec.away_formation), season, site_matchday(spec.seed))
        c = m.context
        side = {p.player_id: t.side for t in (m.home, m.away) for p in t.squad}
        across = sum(1 for r in c.relationships if side.get(r.person_id) and side.get(r.other_id)
                     and side[r.person_id] != side[r.other_id])
        sources = Counter(e.source for e in c.effects)
        form = " / ".join(f"{f.league_position}. {f.points} pts {''.join(f.last_results)}" for f in c.form)
        h = c.head_to_head
        print(f"{spec.match_id:12} round {site_matchday(spec.seed)}  {c.stakes:13} {form}  h2h {h.home_wins}-{h.draws}-"
              f"{h.away_wins} of {h.played}  news {len(c.news)}  ties {across} across, "
              f"{len(c.relationships) - across} within  effects {len(c.effects)} "
              f"(stories {sum(n for s, n in sources.items() if s in STORY)})")


if __name__ == "__main__":
    main()
