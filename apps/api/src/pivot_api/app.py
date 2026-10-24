import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pivot_adapters import build_adapters

from .demo import seed_demo
from .personalize import personalizer_from_env
from .realtime import router as realtime_router
from .routes import router
from .sims import SimStatus, data_dir_from_env, load_sims, specs_from_env

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
    if app.state.adapters.profile == "local" and os.getenv("PIVOT_DEMO", "1") != "0":
        log.info("seeded demo match %s", await seed_demo(app.state.adapters.matches, app.state.adapters.traces))
    # Simulated finished matches (Ax6), loaded in the background so /healthz answers straight away.
    app.state.sims = SimStatus()
    task = None
    if app.state.adapters.profile == "local" and (specs := specs_from_env()):
        task = asyncio.create_task(load_sims(app.state.adapters, specs, data_dir_from_env(), app.state.sims),
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
app.include_router(router)
app.include_router(realtime_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
