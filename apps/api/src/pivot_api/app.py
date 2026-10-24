import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from pivot_adapters import build_adapters

from .demo import seed_demo
from .personalize import personalizer_from_env
from .realtime import router as realtime_router
from .routes import router
from .sims import SimStatus, data_dir_from_env, fixture_from_env, load_fixture, load_sims, specs_from_env

log = logging.getLogger("uvicorn.error")   # shows up in the uvicorn startup log

# The Vite dev server; extra origins come from PIVOT_CORS_ORIGINS (comma separated).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Composition root: the only place the API picks adapters, from PIVOT_PROFILE (default local).
    app.state.adapters = build_adapters()
    log.info("PIVOT_PROFILE=%s", app.state.adapters.profile)
    app.state.personalizer = personalizer_from_env(app.state.adapters.matches)
    # Local profile starts empty, so put one demo match in for frontend work. PIVOT_DEMO=0 turns it off.
    app.state.fixture_frames = {}
    if app.state.adapters.profile == "local" and os.getenv("PIVOT_DEMO", "1") != "0":
        log.info("seeded demo match %s", await seed_demo(app.state.adapters.matches, app.state.adapters.traces))
        # The recorded demo (B02, eval/fixtures/demo-1021): the match the web page opens by default.
        if (fixture := fixture_from_env()) is not None:
            try:
                match_id, frames = await load_fixture(app.state.adapters, fixture)
                if frames is not None:
                    app.state.fixture_frames[match_id] = frames
                log.info("loaded recorded demo %s from %s", match_id, fixture)
            except (OSError, ValueError, KeyError):
                log.exception("could not load the recorded demo from %s", fixture)
    # Simulated finished matches (Ax6), loaded in the background so /healthz answers straight away.
    app.state.sims = SimStatus()
    app.state.sims_dir = data_dir_from_env()
    task = None
    if app.state.adapters.profile == "local" and (specs := specs_from_env()):
        task = asyncio.create_task(load_sims(app.state.adapters, specs, app.state.sims_dir, app.state.sims),
                                   name="sims")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


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
app.include_router(realtime_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
