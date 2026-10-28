#!/usr/bin/env python3
"""Write every result the site serves for some of its matches into the shared stores, ahead of the viewers
(#364): the simulation (Blob), the turning points and their explanations, every audience x picked team x
language version, and the first what-if chips of each turning point with their translations (Cosmos).

It runs the site's own startup (pivot_api.single) on this computer, so the stores, models and code paths
are the live site's. Several computers can share the work: give each its own match ids.

  uv run scripts/generate_results.py S2026-27-TES-VAN S2026-29-BRI-FAL ...
  uv run scripts/generate_results.py --part 2/3          # the second third of sims.FIXTURE_IDS

Needs `az login` with an account that can use the Cosmos account, the storage account and the Foundry
models (scripts/generate_results.env lists the settings). Safe to run again: stored results are reused.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

LANGS = ("en", "zh", "es")
CHIPS_PER_PIVOT = 3


def match_ids(argv: list[str]) -> list[str]:
    from pivot_api.sims import FIXTURE_IDS
    if argv and argv[0] == "--part":
        k, n = (int(x) for x in argv[1].split("/"))
        size = -(-len(FIXTURE_IDS) // n)
        return list(FIXTURE_IDS[(k - 1) * size:k * size])
    return argv or list(FIXTURE_IDS)


async def main(ids: list[str]) -> None:
    os.environ["PIVOT_SIM_MATCHES"] = "0"                 # only the matches given here
    os.environ["PIVOT_SIM_FIXTURES"] = ",".join(ids)
    from pivot_api.single import build_app
    from pivot_core.domain.narrative import ViewerPrefs

    log = logging.getLogger("generate")
    app = build_app()
    started = time.monotonic()
    async with app.router.lifespan_context(app):
        repo, pers = app.state.adapters.matches, app.state.personalizer
        log.info("GEN: %d matches: %s", len(ids), ",".join(ids))
        while [m for m in ids if await repo.get_match(m) is None]:
            await asyncio.sleep(10)
        log.info("GEN: all matches simulated after %.0fs", time.monotonic() - started)
        gate = asyncio.Semaphore(2)                       # model calls: two matches at a time

        async def texts(match_id: str) -> dict[str, int]:
            async with gate:
                deadline = time.monotonic() + 3600        # the worker writes the turning points first
                while time.monotonic() < deadline:
                    pivots = await repo.list_pivots(match_id)
                    if pivots and all(p.status == "rejected" or p.narrative is not None for p in pivots):
                        break
                    await asyncio.sleep(10)
                counts = {"llm": 0, "template": 0}
                for pivot in await repo.list_pivots(match_id):
                    if pivot.status == "rejected" or pivot.narrative is None:
                        continue
                    for team in (None, "home", "away"):
                        for audience in ("analyst", "fan"):
                            for lang in LANGS:
                                prefs = ViewerPrefs(audience=audience, language=lang, focus_team=team)
                                try:
                                    got = await pers.personalize(pivot, prefs)
                                except Exception:
                                    log.warning("%s %s failed", pivot.pivot_id, prefs, exc_info=True)
                                    continue
                                counts["llm" if got.pivot.narrative.source == "llm" else "template"] += 1
                log.info("GEN: %s explanations %s (%.0fs)", match_id, counts, time.monotonic() - started)
                return counts

        async def whatifs() -> None:
            for match_id in ids:                          # one match at a time: the queue never fills up
                await app.state.whatif.warm(match_id, CHIPS_PER_PIVOT, wait=3600)
                n = await app.state.whatif.prewarm(match_id, ["zh", "es"], wait=4 * 3600)
                log.info("GEN: %s what-if done, %d translations (%.0fs)", match_id, n, time.monotonic() - started)

        await asyncio.gather(asyncio.gather(*[texts(m) for m in ids]), whatifs())
        scen = app.state.whatif.scenarios.values()
        log.info("GEN: DONE in %.0fs. what-ifs completed %d, failed %d", time.monotonic() - started,
                 sum(s.status == "completed" for s in scen), sum(s.status == "failed" for s in scen))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("azure", "httpx", "agent_framework"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    asyncio.run(main(match_ids(sys.argv[1:])))
