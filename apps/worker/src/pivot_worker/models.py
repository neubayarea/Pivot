"""Model access for the agents: one call shape, two tiers, bounded retries (ADR-0004).

Every model call goes through a `ModelClient`. `FoundryModelClient` talks to the two Foundry
deployments with Entra ID tokens (a service principal on the Oracle VM, `az login` locally; no
API keys); `OfflineModelClient` is the local stand-in that is always unavailable, so the workflow
degrades to its deterministic fallbacks; `ScriptedModelClient` replays canned replies in tests.

Whatever goes wrong inside a call (sign-in, 4xx, 5xx, timeouts) surfaces as `ModelUnavailable`,
so callers handle a single exception.
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

Tier = Literal["standard", "mini"]
RETRIES = 2                                   # after a timeout, a 429 or a 5xx (ADR-0004)
BACKOFF_SECONDS = 0.5
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
# Request parameters some deployments refuse with a 400 (reasoning models take no temperature).
OPTIONAL_PARAMS = ("temperature", "response_format")


class ModelUnavailable(Exception):
    """The model could not answer: timed out, throttled, refused or misconfigured. The caller degrades."""


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


def credential_from_env():
    """The Entra ID credential for Foundry.

    With AZURE_CLIENT_SECRET set (the Oracle VM) it is that service principal and nothing else.
    Otherwise it is the developer's `az login` and friends, but never managed identity: off Azure
    its probe goes to 169.254.169.254, which on Oracle Cloud is OCI's own metadata service.
    """
    from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential

    secret = os.getenv("AZURE_CLIENT_SECRET")
    if secret:
        missing = [k for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID") if not os.getenv(k)]
        if missing:
            raise ValueError(f"AZURE_CLIENT_SECRET is set but {', '.join(missing)} is not")
        return ClientSecretCredential(os.environ["AZURE_TENANT_ID"], os.environ["AZURE_CLIENT_ID"], secret)
    return DefaultAzureCredential(exclude_managed_identity_credential=True)


def _retryable(e: Exception) -> bool:
    from openai import APIConnectionError, InternalServerError, RateLimitError

    # APIConnectionError covers APITimeoutError; TimeoutError is our own bound on token + request.
    return isinstance(e, RateLimitError | APIConnectionError | InternalServerError | TimeoutError)


def _refused_param(e: Exception, sent: dict) -> str | None:
    """The optional parameter a 400 complains about, if any (e.g. temperature on a reasoning model)."""
    from openai import BadRequestError

    if not isinstance(e, BadRequestError):
        return None
    param = getattr(e, "param", None)
    for name in OPTIONAL_PARAMS:
        if name in sent and (param == name or name in str(e)):
            return name
    return None


class FoundryModelClient:
    """The standard and mini Foundry deployments, named by PIVOT_MODEL_STANDARD and PIVOT_MODEL_MINI."""

    def __init__(self, endpoint: str, deployments: dict[str, str], api_version: str = "2024-10-21", *,
                 client=None) -> None:
        self.deployments = deployments
        # Parameters each deployment has refused once; they are left out from then on.
        self.refused: dict[str, set[str]] = {}
        if client is not None:
            self.client = client
            return
        from azure.identity.aio import get_bearer_token_provider
        from openai import AsyncAzureOpenAI

        token = get_bearer_token_provider(credential_from_env(), TOKEN_SCOPE)
        self.client = AsyncAzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=token,
                                       api_version=api_version, max_retries=0)

    async def complete_json(self, tier: Tier, messages: list[dict[str, str]], *, timeout: float) -> ModelReply:
        deployment = self.deployments[tier]
        refused = self.refused.setdefault(deployment, set())
        attempt = 0
        while True:
            params = {"response_format": {"type": "json_object"}, "temperature": 0.2}
            params = {k: v for k, v in params.items() if k not in refused}
            try:
                # The bound covers fetching the token as well as the request itself.
                async with asyncio.timeout(timeout):
                    r = await self.client.chat.completions.create(
                        model=deployment, messages=messages, timeout=timeout, **params)
                usage = r.usage.total_tokens if r.usage else 0
                return ModelReply(text=r.choices[0].message.content or "", model=deployment, tokens=usage)
            except Exception as e:
                if name := _refused_param(e, params):
                    refused.add(name)             # retry at once without it; does not use up a retry
                    continue
                if not _retryable(e) or attempt == RETRIES:
                    raise ModelUnavailable(f"{deployment}: {type(e).__name__}") from e
                await asyncio.sleep(BACKOFF_SECONDS * 2**attempt)
                attempt += 1


def model_client_from_env() -> ModelClient:
    endpoint = os.getenv("PIVOT_FOUNDRY_ENDPOINT")
    if not endpoint:
        return OfflineModelClient()
    return FoundryModelClient(endpoint, {"standard": os.environ["PIVOT_MODEL_STANDARD"],
                                         "mini": os.environ["PIVOT_MODEL_MINI"]},
                              os.getenv("PIVOT_FOUNDRY_API_VERSION", "2024-10-21"))
