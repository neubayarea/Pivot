import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from pivot_adapters import build_adapters, build_sim_store
from pivot_worker.models import model_client_from_env

from .demo import seed_demo
from .personalize import personalizer_from_env
from .players import router as players_router
from .realtime import router as realtime_router
from .routes import router
from .sims import Replay, SimStatus, data_dir_from_env, fixture_from_env, load_fixture, load_sims, specs_from_env
from .whatif import DEFAULT_WARM, WhatIf
from .whatif import router as whatif_router

log = logging.getLogger("uvicorn.error")   # shows up in the uvicorn startup log

# The Vite dev server; extra origins come from PIVOT_CORS_ORIGINS (comma separated).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Composition root: the only place the API picks adapters, from PIVOT_PROFILE (default local).
    app.state.adapters = build_adapters()
    log.info("PIVOT_PROFILE=%s", app.state.adapters.profile)
    app.state.personalizer = personalizer_from_env(app.state.adapters.matches)
    # Local profile starts empty, so the recorded demo goes in. PIVOT_DEMO=0 turns it off. The hand-made
    # sample (demo.py, its narratives written by hand, never verified) is test data only: PIVOT_SAMPLE_MATCH=1 (Ax54).
    app.state.fixture_frames = {}
    app.state.fixture_files = {}
    # players.py: per-player numbers, worked out once per match on first use
    app.state.player_calcs, app.state.player_lines, app.state.player_calcs_lock = {}, {}, asyncio.Lock()
    replays: dict[str, Replay] = {}           # how each stored match was simulated, for the what-if replays
    demo_id = None
    if app.state.adapters.profile == "local" and os.getenv("PIVOT_DEMO", "1") != "0":
        if os.getenv("PIVOT_SAMPLE_MATCH", "0") == "1":
            log.info("seeded sample match %s", await seed_demo(app.state.adapters.matches, app.state.adapters.traces))
        # The recorded demo (B02, eval/fixtures/demo-1021): the match the web page opens by default.
        if (fixture := fixture_from_env()) is not None:
            try:
                match_id, frames = await load_fixture(app.state.adapters, fixture, replays)
                demo_id = match_id
                app.state.fixture_files[match_id] = fixture       # its saved player lines (players.py)
                if frames is not None:
                    app.state.fixture_frames[match_id] = frames
                log.info("loaded recorded demo %s from %s", match_id, fixture)
            except (OSError, ValueError, KeyError):
                log.exception("could not load the recorded demo from %s", fixture)
    # Simulated finished matches (Ax6), loaded in the background so /healthz answers straight away.
    app.state.sims = SimStatus()
    app.state.sims_dir = data_dir_from_env()
    tasks = []
    if app.state.adapters.profile == "local" and (specs := specs_from_env()):
        replays.update((spec.match_id, spec.replay()) for spec in specs)
        tasks.append(asyncio.create_task(load_sims(app.state.adapters, specs, app.state.sims_dir, app.state.sims,
                                              store=build_sim_store()),
                                         name="sims"))
    # What-if replays (A09): one at a time in the background; the recorded demo's chips run first.
    app.state.whatif = WhatIf.from_env(app.state.adapters, replays, model_client_from_env())
    app.state.whatif.start()
    # Chinese and Spanish versions of the demo's pivots (Ax35), written once the worker has the English ones,
    # and of its finished what-ifs (Ax39), once the warm-up has run.
    langs = [x.strip() for x in (os.getenv("PIVOT_PREWARM_LANGS") or "zh,es").split(",")
             if x.strip() in ("zh", "es")]
    if demo_id is not None:
        warm = int(os.getenv("PIVOT_WHATIF_WARM") or DEFAULT_WARM)
        tasks.append(asyncio.create_task(_warm_whatif(app.state.whatif, demo_id, warm, langs), name="whatif-warm"))
    prewarm = [m.strip() for m in (os.getenv("PIVOT_PREWARM_MATCHES") or demo_id or "").split(",") if m.strip()]
    if langs and prewarm:
        tasks.append(asyncio.create_task(_prewarm(app.state.personalizer, prewarm, langs), name="prewarm"))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await app.state.whatif.stop()
        if app.state.adapters.results is not None:
            await app.state.adapters.results.close()


async def _prewarm(personalizer, match_ids: list[str], langs: list[str]) -> None:
    for match_id in match_ids:
        try:
            log.info("prewarmed %s in %s: %d versions stored", match_id, ",".join(langs),
                     await personalizer.prewarm(match_id, langs))
        except Exception:
            log.exception("prewarm of %s failed", match_id)


async def _warm_whatif(whatif: WhatIf, match_id: str, per_pivot: int, langs: list[str]) -> None:
    try:
        if per_pivot > 0:
            await whatif.warm(match_id, per_pivot)
        if langs:
            log.info("what-if comparisons of %s translated into %s: %d", match_id, ",".join(langs),
                     await whatif.prewarm(match_id, langs))
    except Exception:
        log.exception("what-if warm-up of %s failed", match_id)


app = FastAPI(title="Pivot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + [o.strip() for o in os.getenv("PIVOT_CORS_ORIGINS", "").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Tracking frames are ~1.7 KB of JSON a second of play; gzip takes a five-minute window to ~60 KB.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(router)
app.include_router(players_router)
app.include_router(realtime_router)
app.include_router(whatif_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
