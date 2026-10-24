"""The AI's results in Azure Cosmos DB for NoSQL (Ax11): a `ResultBackend` for `ResultStore`.

One container, `results`, partitioned by `/match_id`, one item per result:

  {"id": <hash of version, kind, name>, "match_id", "version", "kind", "name", "data": <the result's JSON>}

Opening a match is one query inside its partition: the items of this version come back, the
others (an older version) are deleted, and so are the ones `ResultStore` drops. Writes are
single upserts. Nothing queries across partitions, and the container indexes nothing (we only
ever read a whole partition), so writes stay cheap on the database's shared free-tier throughput.
The SDK retries throttled (429) requests itself.

Sign-in is Entra ID through DefaultAzureCredential: the service principal's AZURE_* variables on
the server, `az login` on a laptop. Data-plane roles cannot create containers, so the container is
made once with the Azure CLI (docs/deploy-oracle.md); `connect` tries to create it and says so if it
cannot. Tests pass `azure.fakes.FakeContainer.opener` instead of `open_container`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pivot_adapters.local.results import KINDS, Stored

log = logging.getLogger("pivot_adapters.results")

CONTAINER = "results"
CONNECT_SECONDS = 15                          # the recorded demo waits for this before the site answers
DEFAULT_DATABASE = "pivot"
INDEXING = {"indexingMode": "consistent", "automatic": True, "includedPaths": [], "excludedPaths": [{"path": "/*"}]}
CREATE_HINT = ("az cosmosdb sql container create -g <group> -a <account> -d {db} -n " + CONTAINER
               + " -p /match_id   # no --throughput: it uses the database's shared throughput")


class Container(Protocol):
    """The part of `azure.cosmos.aio.ContainerProxy` we use."""

    def query_items(self, query: str, *, partition_key: Any, **kwargs: Any) -> Any: ...   # async iterator

    async def upsert_item(self, body: dict, **kwargs: Any) -> dict: ...

    async def delete_item(self, item: str, partition_key: Any, **kwargs: Any) -> None: ...


async def open_container(endpoint: str, database: str) -> tuple[Container, Callable[[], Awaitable[None]]]:
    """The real container, signed in with DefaultAzureCredential, and what closes its client."""
    from azure.cosmos import PartitionKey
    from azure.cosmos.aio import CosmosClient
    from azure.cosmos.exceptions import CosmosHttpResponseError
    from azure.identity.aio import DefaultAzureCredential

    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)   # every request
    credential = DefaultAzureCredential()
    client = CosmosClient(endpoint, credential=credential)

    async def close() -> None:
        await client.close()
        await credential.close()

    try:
        db = client.get_database_client(database)
        try:
            container = await db.create_container_if_not_exists(
                id=CONTAINER, partition_key=PartitionKey(path="/match_id"), indexing_policy=INDEXING)
        except CosmosHttpResponseError as exc:
            if exc.status_code == 403:
                raise RuntimeError(f"cannot create the Cosmos container; make it once with: "
                                   f"{CREATE_HINT.format(db=database)}") from exc
            raise
        return container, close
    except BaseException:
        await close()
        raise


def _id(key: str, kind: str, name: str) -> str:
    return hashlib.sha256(f"{key}\n{kind}\n{name}".encode()).hexdigest()[:40]   # no characters Cosmos refuses


class CosmosResults:
    """`ResultBackend` on a Cosmos DB container; see the module docstring."""

    def __init__(self, endpoint: str, database: str = DEFAULT_DATABASE, opener=None) -> None:
        self.endpoint = endpoint
        self.database = database
        self._opener = opener                 # None: `open_container`, looked up when connecting
        self._container: Container | None = None
        self._close: Callable[[], Awaitable[None]] | None = None
        self.request_charge = 0.0             # RUs spent so far, from the x-ms-request-charge headers

    @classmethod
    def from_env(cls) -> CosmosResults:
        endpoint = os.getenv("PIVOT_COSMOS_ENDPOINT", "").strip()
        return cls(endpoint, os.getenv("PIVOT_COSMOS_DATABASE", "").strip() or DEFAULT_DATABASE)

    def _charge(self, headers: Any, *_: Any) -> None:
        try:
            self.request_charge += float(headers.get("x-ms-request-charge", 0))
        except (TypeError, ValueError, AttributeError):
            pass

    async def connect(self) -> None:
        if not self.endpoint:
            raise RuntimeError("PIVOT_COSMOS_ENDPOINT is not set")
        self._container, self._close = await asyncio.wait_for(
            (self._opener or open_container)(self.endpoint, self.database), CONNECT_SECONDS)
        log.info("AI results are kept in Cosmos DB %s, database %s, container %s", self.endpoint, self.database,
                 CONTAINER)

    async def close(self) -> None:
        if self._close is not None:
            await self._close()
            self._close = None

    async def load(self, match_id: str, key: str) -> Stored:
        assert self._container is not None
        before = self.request_charge
        stored: Stored = {kind: [] for kind in KINDS}
        stale = []
        named = []
        async for item in self._container.query_items("SELECT * FROM c", partition_key=match_id,
                                                      response_hook=self._charge):
            if item.get("version") != key:
                stale.append(item["id"])
            elif item.get("kind") in stored:
                named.append(item)
        for item in sorted(named, key=lambda i: i.get("name", "")):
            stored[item["kind"]].append((item["id"], item.get("data")))
        if stale:
            log.info("%s: removing %d results of other versions from Cosmos DB", match_id, len(stale))
            await self.delete(match_id, key, stale)
        log.info("%s: %d results read from Cosmos DB (%.1f RU)", match_id, len(named), self.request_charge - before)
        return stored

    async def delete(self, match_id: str, key: str, handles: list[str]) -> None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        assert self._container is not None
        limit = asyncio.Semaphore(8)

        async def one(item_id: str) -> None:
            async with limit:
                try:
                    await self._container.delete_item(item_id, partition_key=match_id, response_hook=self._charge)
                except CosmosResourceNotFoundError:
                    pass
                except Exception:            # left behind, dropped again on the next start
                    log.warning("could not remove result %s of %s from Cosmos DB", item_id, match_id, exc_info=True)

        await asyncio.gather(*(one(h) for h in handles))

    async def write(self, match_id: str, key: str, kind: str, name: str, data: dict) -> None:
        assert self._container is not None
        body = {"id": _id(key, kind, name), "match_id": match_id, "version": key, "kind": kind, "name": name,
                "data": data}
        try:
            await self._container.upsert_item(body, response_hook=self._charge)
        except Exception:                    # the result stays in memory for this run
            log.warning("could not write %s %s of %s to Cosmos DB; kept in memory only", kind, name, match_id,
                        exc_info=True)
