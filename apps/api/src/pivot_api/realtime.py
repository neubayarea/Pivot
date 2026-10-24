"""Local realtime push (profile L, ADR-0007): a WebSocket per match on top of the in-process publisher.

    ws://127.0.0.1:8000/api/ws/matches/{match_id}?since={last seq received}

Every frame is one `Envelope` as JSON, `{type, match_id, seq, ts, payload}`, seq strictly
increasing per match. With `since`, the server first resends the envelopes it still holds with
seq > since, then goes live; without it, only live envelopes are sent. In the cloud the browser
connects to Web PubSub instead (same frames, no resend), which `POST /api/negotiate` decides.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from pivot_core.domain import Envelope
from pivot_core.domain.realtime import MessageType

router = APIRouter(prefix="/api")

UNKNOWN_MATCH = 4404       # WebSocket close codes 4000-4999 are free for applications
NOT_LOCAL = 4501


@router.websocket("/ws/matches/{match_id}")
async def match_feed(ws: WebSocket, match_id: str, since: int | None = None) -> None:
    adapters = ws.app.state.adapters
    live = adapters.live
    await ws.accept()
    if not hasattr(live, "subscribe"):
        await ws.close(NOT_LOCAL, "realtime goes through Web PubSub in this profile; call /api/negotiate")
        return
    if await adapters.matches.get_match(match_id) is None:
        await ws.close(UNKNOWN_MATCH, f"match {match_id!r} not found")
        return

    async with live.subscribe(match_id) as sub:   # subscribe before replaying so nothing falls in between
        last = -1
        if since is not None:
            if since > live.last_seq(match_id):   # the server restarted and seq began again
                since = -1
            for envelope in live.replay(match_id, since):
                await ws.send_json(envelope.model_dump(mode="json"))
                last = envelope.seq

        async def push() -> None:
            nonlocal last
            async for envelope in sub:
                if envelope.seq > last:           # already sent during the replay
                    await ws.send_json(envelope.model_dump(mode="json"))
                    last = envelope.seq

        async def drain() -> None:                # clients send nothing; this only notices the disconnect
            with contextlib.suppress(WebSocketDisconnect):
                while True:
                    await ws.receive_text()
            tg.cancel_scope.cancel()

        async with anyio.create_task_group() as tg:
            tg.start_soon(push)
            tg.start_soon(drain)


class DevPublish(BaseModel):
    type: MessageType
    payload: dict[str, Any] = {}


@router.post("/dev/matches/{match_id}/publish", status_code=202)
async def dev_publish(request: Request, match_id: str, body: DevPublish) -> Envelope:
    """Local profile only: push one envelope by hand (scripts/ws_demo.py, frontend work before the simulator)."""
    adapters = request.app.state.adapters
    if adapters.profile != "local":
        raise HTTPException(404)
    envelope = Envelope(type=body.type, match_id=match_id, seq=0, ts=datetime.now(UTC).isoformat(),
                        payload=body.payload)
    await adapters.live.publish(envelope)          # the local publisher assigns the real seq
    return adapters.live.replay(match_id, adapters.live.last_seq(match_id) - 1)[-1]
