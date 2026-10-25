"""Simulated match files in Azure Blob Storage (Ax15): a `SimStore` for `pivot_api.sims`.

One container (`PIVOT_BLOB_CONTAINER`, default `sims`), one blob per file, named like the file on
disk: `M-seed-101.<SIM_VERSION>.json.gz` and `.frames.json.gz`. The version is in the name and in the
blob's `sim_version` metadata, so a blob made by other code never matches the current version.
Old versions stay until `scripts/sims_blob.py clean` removes them.

Sign-in is Entra ID through DefaultAzureCredential (the service principal's AZURE_* variables on the
server, `az login` on a laptop); no keys, SAS tokens or connection strings. The container is created
if missing; a role that cannot do that gets the exact Azure CLI command in the log.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from pivot_adapters.local.simstore import SimBlob

log = logging.getLogger("pivot_adapters.sims")

DEFAULT_CONTAINER = "sims"
CONNECT_SECONDS = 20
TRANSFER_SECONDS = 120
CREATE_HINT = "az storage container create --account-name {account} --name {container} --auth-mode login"


class BlobSimStore:
    def __init__(self, endpoint: str, container: str = DEFAULT_CONTAINER) -> None:
        self.endpoint = endpoint
        self.container = container
        self._credential = None
        self._service = None
        self._client = None

    @classmethod
    def from_env(cls) -> BlobSimStore:
        return cls(os.getenv("PIVOT_BLOB_ENDPOINT", "").strip(),
                   os.getenv("PIVOT_BLOB_CONTAINER", "").strip() or DEFAULT_CONTAINER)

    @property
    def account(self) -> str:
        from urllib.parse import urlparse
        return (urlparse(self.endpoint).hostname or "<account>").split(".")[0]

    async def connect(self) -> None:
        if not self.endpoint:
            raise RuntimeError("PIVOT_BLOB_ENDPOINT is not set")
        await asyncio.wait_for(self._connect(), CONNECT_SECONDS)
        log.info("simulated matches are kept in Blob Storage %s, container %s", self.endpoint, self.container)

    async def _connect(self) -> None:
        from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError
        from azure.identity.aio import DefaultAzureCredential
        from azure.storage.blob.aio import BlobServiceClient

        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
        self._credential = DefaultAzureCredential()
        self._service = BlobServiceClient(self.endpoint, credential=self._credential)
        self._client = self._service.get_container_client(self.container)
        try:
            try:
                await self._client.get_container_properties()
            except ResourceNotFoundError:
                try:
                    await self._client.create_container()
                    log.info("created Blob container %s", self.container)
                except ResourceExistsError:
                    pass
                except HttpResponseError as exc:
                    if exc.status_code == 403:
                        raise RuntimeError("the Blob container does not exist and this identity cannot create it; "
                                           "make it once with: "
                                           + CREATE_HINT.format(account=self.account, container=self.container)) from exc
                    raise
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        for resource in (self._service, self._credential):
            if resource is not None:
                try:
                    await resource.close()
                except Exception:
                    pass
        self._service = self._credential = self._client = None

    async def list(self) -> list[SimBlob]:
        assert self._client is not None
        return [SimBlob(b.name, b.size or 0) async for b in self._client.list_blobs()]

    async def download(self, name: str, dest: Path) -> bool:
        from azure.core.exceptions import ResourceNotFoundError

        assert self._client is not None
        try:
            stream = await self._client.get_blob_client(name).download_blob(timeout=TRANSFER_SECONDS)
        except ResourceNotFoundError:
            return False
        with dest.open("wb") as fh:
            await stream.readinto(fh)
        return True

    async def upload(self, name: str, src: Path, version: str) -> None:
        assert self._client is not None
        with src.open("rb") as fh:
            await self._client.get_blob_client(name).upload_blob(
                fh, overwrite=True, metadata={"sim_version": version}, timeout=TRANSFER_SECONDS)

    async def delete(self, names: list[str]) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        assert self._client is not None
        for name in names:
            try:
                await self._client.delete_blob(name)
            except ResourceNotFoundError:
                pass
