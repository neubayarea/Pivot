"""Single-process mode for one-VM deploys: `uv run python -m pivot_api.single`.

One uvicorn process serves the API (with its WebSocket), runs the worker loop and the
simulator, and serves the built web app, all on one port and one set of local adapters.
That is what makes worker pushes reach the browser: the local queue and live publisher only
work inside one process (A05, A06). See docs/deploy-oracle.md.

Environment, on top of the API's own:
- `PIVOT_WEB_DIST`: the `pnpm --filter web build` output; default `apps/web/dist` in the repo.
  If it has no index.html, only the API is served.
- `PIVOT_WORKER=0` / `PIVOT_SIMULATOR=0` turn the embedded worker / simulator off.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

import pivot_simulator
import pivot_worker.__main__ as worker_main
from pivot_adapters import Adapters
from pivot_worker.pipeline import FakePipeline
from pivot_worker.worker import Worker

from .app import app as api_app
from .app import lifespan as api_lifespan

log = logging.getLogger("uvicorn.error")

DEFAULT_WEB_DIST = Path(__file__).resolve().parents[4] / "apps" / "web" / "dist"
# Not handed to the SPA: unknown paths here should stay a 404, not turn into index.html.
BACKEND_PREFIXES = ("api/", "healthz")

# Hook for the live simulator (B line): `async def run_live(adapters, stop)` in `pivot_simulator`,
# feeding events into the same adapters. Started here once it exists.
Background = Callable[[Adapters, asyncio.Event], Awaitable[None]]


class SpaStaticFiles(StaticFiles):
    """Static files, with index.html for any other path so client-side routes survive a reload."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            # Starlette hands over an OS path (`api\nope` on Windows); compare with forward slashes.
            if exc.status_code != 404 or path.replace(os.sep, "/").startswith(BACKEND_PREFIXES):
                raise
            return await super().get_response("index.html", scope)


def _enabled(name: str) -> bool:
    return os.getenv(name, "1") != "0"


async def run_worker(adapters: Adapters, stop: asyncio.Event) -> None:
    # Same pipeline choice as `python -m pivot_worker` (D06 adds build_pipeline, PIVOT_PIPELINE=detect).
    build_pipeline = getattr(worker_main, "build_pipeline", lambda _adapters: FakePipeline())
    await Worker(adapters, build_pipeline(adapters)).run(stop)


def background_tasks() -> dict[str, Background]:
    tasks: dict[str, Background] = {}
    if _enabled("PIVOT_WORKER"):
        tasks["worker"] = run_worker
    if _enabled("PIVOT_SIMULATOR"):
        simulator = getattr(pivot_simulator, "run_live", None)
        if simulator is None:
            log.info("simulator has no run_live yet; not started")
        else:
            tasks["simulator"] = simulator
    return tasks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with api_lifespan(app):
        stop = asyncio.Event()
        running = {name: asyncio.create_task(run(app.state.adapters, stop), name=name)
                   for name, run in background_tasks().items()}
        for name, task in running.items():
            task.add_done_callback(_report_exit)
            log.info("started %s in-process", name)
        try:
            yield
        finally:
            stop.set()
            if running:
                await asyncio.wait(running.values(), timeout=5)
            for task in running.values():
                task.cancel()


def _report_exit(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        log.error("%s stopped", task.get_name(), exc_info=task.exception())


def mount_web(app: FastAPI, dist: Path) -> bool:
    if not (dist / "index.html").is_file():
        log.warning("no web build at %s; serving the API only", dist)
        return False
    app.mount("/", SpaStaticFiles(directory=dist, html=True), name="web")
    return True


def build_app(dist: Path | None = None) -> FastAPI:
    """The API's routes and middleware, plus the worker/simulator lifespan and the web build mounted last."""
    app = FastAPI(title="Pivot", lifespan=lifespan)
    app.user_middleware = list(api_app.user_middleware)
    app.router.routes.extend(api_app.router.routes)
    mount_web(app, dist or Path(os.getenv("PIVOT_WEB_DIST") or DEFAULT_WEB_DIST))
    return app


def main() -> None:
    uvicorn.run(build_app(), host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")),
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
