"""Model access for the agents: one call shape, two tiers, bounded retries (ADR-0004).

Every model call goes through a `ModelClient`. `FoundryModelClient` talks to the two Foundry
deployments with the `az login` / managed identity (no keys); `OfflineModelClient` is the
local stand-in that is always unavailable, so the workflow degrades to its deterministic
fallbacks; `ScriptedModelClient` replays canned replies in tests.
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

Tier = Literal["standard", "mini"]
RETRIES = 2                                   # after a timeout or a 429 (ADR-0004)
BACKOFF_SECONDS = 0.5


class ModelUnavailable(Exception):
    """Timed out or throttled even after the retries; the caller degrades."""


@dataclass(frozen=True)
class ModelReply:
    text: str
    model: str
    tokens: int = 0


class ModelClient(Protocol):
    async def complete_json(self, tier: Tier, messages: list[dict[str, str]], *, timeout: float) -> ModelReply: ...


class OfflineModelClient:
    """No model at all: every call is unavailable, so the workflow runs on its fallbacks."""

    async def complete_json(self, tier: Tier, messages: list[dict[str, str]], *, timeout: float) -> ModelReply:
        raise ModelUnavailable("no model configured (set PIVOT_FOUNDRY_ENDPOINT)")


class ScriptedModelClient:
    """Test double: hands out queued replies per tier. An exception in the queue is raised."""

    def __init__(self, standard: Iterable[str | Exception] = (), mini: Iterable[str | Exception] = ()) -> None:
        self.queues = {"standard": deque(standard), "mini": deque(mini)}
        self.calls: list[tuple[Tier, list[dict[str, str]]]] = []

    async def complete_json(self, tier: Tier, messages: list[dict[str, str]], *, timeout: float) -> ModelReply:
        self.calls.append((tier, messages))
        if not self.queues[tier]:
            raise ModelUnavailable(f"no scripted reply left for {tier}")
        reply = self.queues[tier].popleft()
        if isinstance(reply, Exception):
            raise reply
        return ModelReply(text=reply, model=f"scripted-{tier}", tokens=len(reply) // 4)


class FoundryModelClient:
    """The standard and mini Foundry deployments, named by PIVOT_MODEL_STANDARD and PIVOT_MODEL_MINI."""

    def __init__(self, endpoint: str, deployments: dict[str, str], api_version: str = "2024-10-21") -> None:
        from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
        from openai import AsyncAzureOpenAI

        token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
        self.deployments = deployments
        self.client = AsyncAzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=token,
                                       api_version=api_version, max_retries=0)

    async def complete_json(self, tier: Tier, messages: list[dict[str, str]], *, timeout: float) -> ModelReply:
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        deployment = self.deployments[tier]
        for attempt in range(RETRIES + 1):
            try:
                r = await self.client.chat.completions.create(
                    model=deployment, messages=messages, response_format={"type": "json_object"},
                    temperature=0.2, timeout=timeout,
                )
                usage = r.usage.total_tokens if r.usage else 0
                return ModelReply(text=r.choices[0].message.content or "", model=deployment, tokens=usage)
            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                if attempt == RETRIES:
                    raise ModelUnavailable(f"{deployment}: {type(e).__name__}") from e
                await asyncio.sleep(BACKOFF_SECONDS * 2**attempt)
        raise AssertionError("unreachable")


def model_client_from_env() -> ModelClient:
    endpoint = os.getenv("PIVOT_FOUNDRY_ENDPOINT")
    if not endpoint:
        return OfflineModelClient()
    return FoundryModelClient(endpoint, {"standard": os.environ["PIVOT_MODEL_STANDARD"],
                                         "mini": os.environ["PIVOT_MODEL_MINI"]},
                              os.getenv("PIVOT_FOUNDRY_API_VERSION", "2024-10-21"))
