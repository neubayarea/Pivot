import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pivot_adapters import build_adapters

log = logging.getLogger("uvicorn.error")   # shows up in the uvicorn startup log


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Composition root: the only place the API picks adapters, from PIVOT_PROFILE (default local).
    app.state.adapters = build_adapters()
    log.info("PIVOT_PROFILE=%s", app.state.adapters.profile)
    yield


app = FastAPI(title="Pivot API", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
