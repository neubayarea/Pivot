"""Local `LiveNegotiator`: the browser connects straight to the API's own WebSocket (served by A06)."""

from __future__ import annotations

import os
from urllib.parse import urlencode

DEFAULT_WS_URL = "ws://127.0.0.1:8000/api/ws"


class LocalNegotiator:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("PIVOT_WS_URL") or DEFAULT_WS_URL

    async def negotiate(self, match_id: str | None = None) -> str:
        return f"{self.base_url}?{urlencode({'matchId': match_id})}" if match_id else self.base_url
