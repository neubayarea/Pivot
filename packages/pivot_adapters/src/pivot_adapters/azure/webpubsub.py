"""Azure Web PubSub `LivePublisher` and `LiveNegotiator` (ADR-0007).

One group per match, `match.{matchId}`. The browser gets a client access URL that joins it to
that group on connect, and receives the same envelope JSON as on the local WebSocket. Web PubSub
keeps no history, so after a reconnect the client catches up over REST (`/events?since=`).

Both classes take an async `WebPubSubServiceClient` (azure-messaging-webpubsubservice); tests
pass a fake. `from_env` builds the real one with the managed identity (A08 wires it up).
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from pivot_core.domain import Envelope

DEFAULT_HUB = "pivot"
TOKEN_MINUTES = 60


def group_name(match_id: str) -> str:
    return f"match.{match_id}"


class ServiceClient(Protocol):
    """The part of `azure.messaging.webpubsubservice.aio.WebPubSubServiceClient` we use."""

    async def send_to_group(self, group: str, message: Any, *, content_type: str = ..., **kwargs: Any) -> None: ...

    async def get_client_access_token(self, **kwargs: Any) -> dict[str, Any]: ...


def client_from_env() -> ServiceClient:
    """Client for `PIVOT_WEBPUBSUB_ENDPOINT` / `PIVOT_WEBPUBSUB_HUB`, signed in with DefaultAzureCredential."""
    from azure.identity.aio import DefaultAzureCredential
    from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient

    return WebPubSubServiceClient(
        endpoint=os.environ["PIVOT_WEBPUBSUB_ENDPOINT"],
        hub=os.getenv("PIVOT_WEBPUBSUB_HUB", DEFAULT_HUB),
        credential=DefaultAzureCredential(),
    )


class WebPubSubLivePublisher:
    def __init__(self, client: ServiceClient) -> None:
        self._client = client

    async def publish(self, envelope: Envelope) -> None:
        await self._client.send_to_group(
            group_name(envelope.match_id), envelope.model_dump(mode="json"), content_type="application/json",
        )


class WebPubSubNegotiator:
    def __init__(self, client: ServiceClient, minutes_to_expire: int = TOKEN_MINUTES) -> None:
        self._client = client
        self._minutes = minutes_to_expire

    async def negotiate(self, match_id: str | None = None) -> str:
        # `groups` joins the connection to the match group on connect; no joinLeaveGroup role is
        # granted, so a browser cannot listen to other matches or send anything.
        token = await self._client.get_client_access_token(
            groups=[group_name(match_id)] if match_id else None, minutes_to_expire=self._minutes,
        )
        return token["url"]
