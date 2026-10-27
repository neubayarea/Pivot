#!/usr/bin/env python3
"""Run every What-if chip of the recorded demo ahead of time, so the server answers them at once (Bx11, #218).

  uv run scripts/make_whatif_fixture.py                    # all chips, 200, 500 and 1000 runs per arm
  uv run scripts/make_whatif_fixture.py --list             # the chips and what they would cost, nothing run
  uv run scripts/make_whatif_fixture.py --runs 200 --workers 8
  uv run scripts/make_whatif_fixture.py --table            # what is in the file, as a Markdown table
  uv run scripts/make_whatif_fixture.py --match M-seed-101 M-seed-212 --runs 200   # the site's matches (Bx14)

With `--match` the site's simulated matches are run instead of the demo: each one is simulated and stored
as the server does it (`build_one`, `store_one`) and gets its own file, eval/fixtures/whatif/<id>.whatif.json,
keyed by the version a Linux checkout gives the simulator code (`portable_sim_version`), so a file made on
Windows still matches the server. Any change to pivot_core/sim or pivot_core/analytics makes it stale: the
server then logs that and runs the chips itself, so re-run this after such a change.

Goes through the API's own code: the demo is loaded as the server loads it (`load_fixture`), its pivots
come from the worker's fake pipeline (the same minutes and directions the server's worker gives them),
and each chip is asked of `WhatIf` the way a POST asks it, so every spec, seed and cache key is the one
the server would use. Comparisons come from the template (no model is called); the server asks its
model for one when a stored result is first requested.

Writes eval/fixtures/demo-1021.whatif.json, keyed by the demo's version (its content hash): the server
reads it at startup and ignores it when the demo file has changed. Finished chips are written as they
come in, and a re-run with the same demo skips the ones already in the file.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

os.environ["PIVOT_RESULTS"] = "0"          # in memory: nothing from earlier server runs is read back

from pivot_adapters import build_adapters  # noqa: E402
from pivot_api.sims import FIXTURE, Replay, build_one, load_fixture, paths, specs_first, store_one  # noqa: E402
from pivot_api.whatif import (  # noqa: E402
    WhatIf, load_precomputed, portable_sim_version, precomputed_path, seed_precomputed_path, write_precomputed,
)
from pivot_core.domain import Scenario  # noqa: E402
from pivot_worker.models import OfflineModelClient  # noqa: E402
from pivot_worker.pipeline import FakePipeline  # noqa: E402
from pivot_worker.worker import Worker  # noqa: E402

RUNS = (200, 500, 1000)
MAX_SPECS = 40                               # --match looks for the match among the site's first this many


async def pivots(adapters) -> None:
    """The worker's pivots for the stored match: the minutes and directions the server's worker gives them."""
    worker = Worker(adapters, FakePipeline())
    while await worker.run_once(timeout=0.5):
        pass


async def demo(fixture: Path):
    """The demo stored as the server stores it, with the worker's pivots."""
    adapters = build_adapters("local")
    replays: dict[str, Replay] = {}
    match_id, _ = await load_fixture(adapters, fixture, replays)
    await pivots(adapters)
    return adapters, replays, match_id, replays[match_id].version, precomputed_path(fixture)


async def seed(match_id: str, data_dir: Path):
    """A simulated match of the site (Bx14), built and stored as the server does (`build_one`, `store_one`),
    under the version a Linux checkout gives it (`portable_sim_version`), the one the server will match."""
    spec = next((s for s in specs_first(MAX_SPECS) if s.match_id == match_id), None)
    if spec is None:
        raise SystemExit(f"{match_id} is not one of the site's first {MAX_SPECS} simulated matches")
    version = portable_sim_version()
    build_one(spec, data_dir, version)
    adapters = build_adapters("local")
    await store_one(adapters, paths(data_dir, spec, version)[0])
    await pivots(adapters)
    return adapters, {match_id: replace(spec.replay(), version=version)}, match_id, version, \
        seed_precomputed_path(match_id)


def pct(p: float) -> str:
    return f"{p:.0%}"


def score(arm) -> str:
    top = arm.top_scores[0]
    return f"{top.home}-{top.away} ({top.share:.0%})"


async def table(whatif: WhatIf, match_id: str, done: dict[str, Scenario]) -> str:
    """Each chip at each size: who wins, the usual final score and each side's shots, as played -> changed."""
    repo = whatif.adapters.matches
    match = await repo.get_match(match_id)
    home, away = match.home.name, match.away.name
    order, labels = {}, {}
    for pivot in await repo.list_pivots(match_id):
        for i, option in enumerate(await whatif.options(pivot, match)):
            order[pivot.pivot_id, option.type], labels[pivot.pivot_id, option.type] = i, option.label
    rows = [f"| pivot | What-if | runs | {home} win | draw | {away} win | most common score | {home} shots | "
            f"{away} shots |", "|---|---|---:|---|---|---|---|---|---|"]
    for s in sorted(done.values(), key=lambda s: (s.spec.pivot_id, order.get((s.spec.pivot_id, s.spec.type), 9),
                                                 s.spec.n_runs)):
        r, sig = s.result, s.result.significant
        b, c, bs, cs = r.baseline, r.counterfactual, r.baseline_stats, r.counterfactual_stats

        def shift(key: str) -> str:
            mark = " **≠**" if sig.get(key) else ""
            return f"{pct(getattr(b, key))} → {pct(getattr(c, key))}{mark}"

        rows.append(f"| {s.spec.pivot_id.rpartition(':')[2]} | {labels.get((s.spec.pivot_id, s.spec.type), s.spec.type)} "
                    f"| {s.spec.n_runs} | {shift('home_win')} | {shift('draw')} | {shift('away_win')} "
                    f"| {score(bs)} → {score(cs)} | {bs.home.shots.mean:.1f} → {cs.home.shots.mean:.1f} "
                    f"| {bs.away.shots.mean:.1f} → {cs.away.shots.mean:.1f} |")
    return "\n".join(rows)


async def main(args: argparse.Namespace) -> int:
    if not args.match:
        return await run(args, *(await demo(args.fixture)))
    with tempfile.TemporaryDirectory() as tmp:
        for match_id in args.match:
            if code := await run(args, *(await seed(match_id, Path(tmp)))):
                return code
    return 0


async def run(args: argparse.Namespace, adapters, replays: dict[str, Replay], match_id: str, version: str,
              out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    done = load_precomputed(out, version)
    print(f"{match_id}, version {version}: {len(done)} chips already in {out.name}")
    whatif = WhatIf(adapters, replays, OfflineModelClient(), workers=args.workers)
    if args.table:
        print(await table(whatif, match_id, done))
        return 0
    whatif.precomputed[match_id] = done            # chips already in the file are answered from it
    whatif.start()
    wanted: list[tuple[str, str, int, int]] = []      # pivot, type, n_runs, from minute
    try:
        pivots = [p for p in await adapters.matches.list_pivots(match_id) if not args.only or p.pivot_id.endswith(args.only)]
        match = await adapters.matches.get_match(match_id)
        for n_runs in args.runs:                     # all the 200s first: a stop halfway still leaves those
            for pivot in pivots:
                for option in await whatif.options(pivot, match):
                    if option.enabled:
                        wanted.append((pivot.pivot_id, option.type, n_runs, option.at_minute or 0))
        cost = sum(n * (90 - minute) for _, _, n, minute in wanted)
        print(f"{len(wanted)} chips; about {cost * 2 * 2.2 / 53 / max(args.workers, 1) / 60:.0f} min on "
              f"{args.workers} workers (2.2 s a run from 37')")
        if args.list:
            for pivot_id, type_, n_runs, minute in wanted:
                print(f"  {pivot_id:<16} {type_:<20} {n_runs:>5} from {minute + 1}'")
            return 0
        pending: dict[str, tuple[str, str, int]] = {}
        for pivot_id, type_, n_runs, _ in wanted:
            scenario = await whatif.submit(pivot_id, type_, n_runs)
            if whatif._key_of(scenario.scenario_id) in done:
                continue
            pending[scenario.scenario_id] = (pivot_id, type_, n_runs)
        print(f"{len(pending)} to run")
        t0 = time.perf_counter()
        while pending:
            await asyncio.sleep(2)
            for scenario_id in [s for s in pending if whatif.scenarios[s].status in ("completed", "failed")]:
                scenario: Scenario = whatif.scenarios[scenario_id]
                pivot_id, type_, n_runs = pending.pop(scenario_id)
                if scenario.status == "failed":
                    print(f"FAILED {pivot_id} {type_} {n_runs}", file=sys.stderr)
                    continue
                done[whatif._key_of(scenario_id)] = scenario
                write_precomputed(out, match_id, version, done)
                b, c = scenario.result.baseline, scenario.result.counterfactual
                print(f"{time.perf_counter() - t0:7.0f}s  {pivot_id:<16} {type_:<20} {n_runs:>5}  "
                      f"home win {b.home_win:.1%} -> {c.home_win:.1%}, away win {b.away_win:.1%} -> {c.away_win:.1%}",
                      flush=True)
    finally:
        await whatif.stop()
    print(f"{len(done)} chips in {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, nargs="+", default=list(RUNS), choices=RUNS)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--only", help="pivot id suffix, e.g. p79")
    parser.add_argument("--list", action="store_true", help="list the chips and stop")
    parser.add_argument("--table", action="store_true", help="print what is in the file as a Markdown table")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--match", nargs="+", metavar="MATCH_ID",
                        help="the site's simulated matches instead of the demo, e.g. M-seed-101 M-seed-212 (Bx14)")
    sys.exit(asyncio.run(main(parser.parse_args())))
