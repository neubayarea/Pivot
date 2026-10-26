"""Where finished simulated matches are kept besides the server's disk (Ax15): the `SimStore` seam.

The disk (`PIVOT_DATA_DIR/sims/`) is always the cache the API reads from. A `SimStore` is the
copy somewhere else that the disk is filled from and written through to. `FilesSimStore` is the
default and does nothing: the disk is all there is. `azure.blob.BlobSimStore` is Azure Blob Storage.

A store deals in whole files by name (`M-seed-101.<version>.json.gz`, `...frames.json.gz`), the same
names as on disk. What those files hold, and whether a download is whole, is the caller's business
(`pivot_api.sims`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

NAME = re.compile(r"(?P<match_id>[A-Za-z0-9_-]+)\.(?P<version>[^.]+)\.(?P<kind>frames\.)?json\.gz")


@dataclass(frozen=True)
class SimBlob:
    name: str
    size: int

    @property
    def match_id(self) -> str | None:
        return m["match_id"] if (m := NAME.fullmatch(self.name)) else None

    @property
    def version(self) -> str | None:
        return m["version"] if (m := NAME.fullmatch(self.name)) else None


class SimStore(Protocol):
    """Everything the API and `scripts/sims_blob.py` ask of a place that keeps match files."""

    async def connect(self) -> None:
        """Raises if the store cannot be used (unreachable, unauthorized); the caller then does without."""

    async def close(self) -> None: ...

    async def list(self) -> list[SimBlob]: ...

    async def download(self, name: str, dest: Path) -> bool:
        """Write the file to `dest` (a temporary path; the caller renames it). False if there is none."""

    async def upload(self, name: str, src: Path, version: str) -> None: ...

    async def delete(self, names: list[str]) -> None: ...


class FilesSimStore:
    """No store beyond the disk: nothing to fetch, nothing to write through."""

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def list(self) -> list[SimBlob]:
        return []

    async def download(self, name: str, dest: Path) -> bool:
        return False

    async def upload(self, name: str, src: Path, version: str) -> None:
        pass

    async def delete(self, names: list[str]) -> None:
        pass
