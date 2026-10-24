"""An in-memory stand-in for a Cosmos DB container, for tests: the calls `CosmosResults` makes, nothing else."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any


class FakeContainer:
    """Items by (partition key, id). Every call costs 1 RU and is counted in `calls`."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}
        self.calls: Counter[str] = Counter()

    async def opener(self, endpoint: str, database: str):
        """Stands in for `open_container`."""
        async def close() -> None:
            pass
        return self, close

    def _charge(self, kwargs: dict, name: str) -> None:
        self.calls[name] += 1
        if hook := kwargs.get("response_hook"):
            hook({"x-ms-request-charge": "1"}, None)

    async def query_items(self, query: str, *, partition_key: Any, **kwargs: Any):
        assert query == "SELECT * FROM c" and partition_key is not None   # never across partitions
        self._charge(kwargs, "query")
        for (pk, _), item in list(self.items.items()):
            if pk == partition_key:
                yield copy.deepcopy(item)

    async def upsert_item(self, body: dict, **kwargs: Any) -> dict:
        self._charge(kwargs, "upsert")
        self.items[(body["match_id"], body["id"])] = copy.deepcopy(body)
        return body

    async def delete_item(self, item: str, partition_key: Any, **kwargs: Any) -> None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        self._charge(kwargs, "delete")
        if self.items.pop((partition_key, item), None) is None:
            raise CosmosResourceNotFoundError(message=f"{item} not found")
