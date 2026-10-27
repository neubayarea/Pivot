"""Work out the next round's pre-match predictions ahead of time (C14, #354).

Each fixture of matchday 31 is played 200 times from kick-off (the What-if runner's baseline arm,
nothing changed) and the result is written to eval/fixtures/next-round/matchday-31.json, which the
API reads at startup (apps/api/src/pivot_api/nextround.py). The file names the simulator version
as a Linux checkout works it out (`portable_sim_version`), so a file made on Windows is used on the
server. Rerun it whenever the simulator changes.

    uv run scripts/make_next_round.py [--matchday 31] [--runs 200] [--workers 10]

C15: `--matchday` works out a later round into its own file (matchday-<n>.json); the page says how
many runs each prediction has.
"""

from __future__ import annotations

import argparse
import json
import time

from pivot_api import sims
from pivot_api.nextround import N_RUNS, NEXT_MATCHDAY, fixtures, next_match, path_for, predict
from pivot_api.whatif import portable_sim_version


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=N_RUNS)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--matchday", type=int, default=NEXT_MATCHDAY)
    args = ap.parse_args()
    path = path_for(args.matchday)
    season = sims._season()
    version = portable_sim_version()
    # A fixture already worked out for this simulator and run count is kept (about 3.5 min each on 12 cores).
    old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    kept = ({f["match_id"]: f["prediction"] for f in old.get("fixtures", [])}
            if old.get("sim_version") == version and old.get("n_runs") == args.runs else {})
    out = []
    for fx in fixtures(args.matchday):
        match = next_match(fx, season)
        t0 = time.monotonic()
        prediction = kept.get(match.match_id) or predict(match, args.runs, args.workers)
        out.append({"match_id": match.match_id, "home": match.home.club_id, "away": match.away.club_id,
                    "seed": match.seed, "prediction": prediction})
        print(f"{match.match_id}: {prediction['home_win']:.2f} / {prediction['draw']:.2f} / {prediction['away_win']:.2f}"
              f", xG {prediction['xg']['home']}-{prediction['xg']['away']} ({time.monotonic() - t0:.0f} s)", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"sim_version": version, "matchday": args.matchday, "n_runs": args.runs, "fixtures": out}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
