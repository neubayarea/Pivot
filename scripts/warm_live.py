#!/usr/bin/env python3
"""Warm the live site after a deploy, so judges and the video never wait on a cold 20-30 s load.

    uv run scripts/warm_live.py [--base https://pivot.in-stacks.com] [--workers 3] [--slow 5]

Takes the match list from GET /api/hub (every hub match, the live one included) and, for each, asks
for what the match pages read: the team stats, the analyst's report, the player stats, the shot map,
the pass network (whole match and each half), the average positions, the heatmaps, the pre-match
numbers and the pre-match sentences in Chinese and Spanish. For the demo match and the live one it
also lists the What-if chips of every turning point.

Read-only: GET requests only, so nothing is computed or stored beyond the server's own caches (no
POST, no what-if run). A few at a time, since the server has two cores. Prints every request slower
than --slow seconds or not answered 200, then a one-line summary; exits 1 if any request failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

DEFAULT_BASE = "https://pivot.in-stacks.com"
DEMO = "S2026-27-TES-VAN"                      # the video's match (docs/submission/video-script.md)
TIMEOUT_S = 120

MATCH_PATHS = (
    "stats", "analysis", "players/stats", "shots", "pass-network", "pass-network?period=1",
    "pass-network?period=2", "positions", "heatmaps", "prematch", "prematch/text?lang=zh",
    "prematch/text?lang=es",
)


def get(base: str, path: str) -> tuple[str, int, float, bytes]:
    """(path, HTTP status or 0 for no answer, seconds, body)."""
    start = time.monotonic()
    req = urllib.request.Request(base + path, headers={"accept": "application/json", "user-agent": "pivot-warm-live"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        body, status = e.read(), e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        body, status = str(e).encode(), 0
    return path, status, time.monotonic() - start, body


def match_ids(hub: dict) -> list[str]:
    """Every hub match, the live one first, each once."""
    live = (hub.get("live") or {}).get("match_id")
    ids = [live] if live else []
    ids += [m["match_id"] for m in hub.get("matches", []) if m.get("match_id")]
    return list(dict.fromkeys(ids))


def pivot_ids(body: bytes) -> list[str]:
    data = json.loads(body)
    rows = data if isinstance(data, list) else data.get("pivots", [])
    return [p["pivot_id"] for p in rows if isinstance(p, dict) and p.get("pivot_id")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"the site to warm (default {DEFAULT_BASE})")
    ap.add_argument("--workers", type=int, default=3, help="requests at a time (default 3; the server has 2 cores)")
    ap.add_argument("--slow", type=float, default=5.0, help="report requests slower than this many seconds (default 5)")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    path, status, secs, body = get(base, "/api/hub")
    if status != 200:
        print(f"GET /api/hub: {status or 'no answer'} after {secs:.1f} s; nothing warmed", file=sys.stderr)
        return 1
    hub = json.loads(body)
    ids = match_ids(hub)
    live = (hub.get("live") or {}).get("match_id")
    paths = [f"/api/matches/{quote(i)}/{p}" for i in ids for p in MATCH_PATHS]
    with_whatif = [i for i in dict.fromkeys([DEMO, live]) if i]
    for i in with_whatif:
        _, s, _, b = get(base, f"/api/matches/{quote(i)}/pivots")
        if s == 200:
            paths += [f"/api/pivots/{quote(p)}/scenarios" for p in pivot_ids(b)]
        else:
            print(f"GET /api/matches/{i}/pivots: {s or 'no answer'}; its What-if chips are not warmed")
    print(f"warming {len(paths)} requests for {len(ids)} matches at {base}, {args.workers} at a time "
          f"(What-if chips for {', '.join(with_whatif)})")

    start = time.monotonic()
    flagged, failed = [], 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for path, status, secs, _ in pool.map(lambda p: get(base, p), paths):
            if status != 200 or secs > args.slow:
                flagged.append((secs, status, path))
                failed += status != 200
                print(f"{secs:6.1f} s  {status or 'no answer':>9}  {path}", flush=True)
    print(f"done in {time.monotonic() - start:.0f} s: {len(paths)} requests, {len(flagged)} slower than "
          f"{args.slow:g} s or not 200, {failed} not 200")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
