#!/usr/bin/env python3
"""Generate the simulated matches on this computer and keep them in Azure Blob Storage (Ax15).

  uv run scripts/sims_blob.py generate-upload --count 50     # simulate (what is not in Blob yet) and upload
  uv run scripts/sims_blob.py generate-upload --seeds 101,212
  uv run scripts/sims_blob.py list                           # what Blob holds, per version, with sizes
  uv run scripts/sims_blob.py clean                          # dry run: what of other versions would go
  uv run scripts/sims_blob.py clean --yes-delete             # really delete it

Blob is read from PIVOT_BLOB_ENDPOINT (or --endpoint) and PIVOT_BLOB_CONTAINER (default `sims`),
signed in with `az login` (DefaultAzureCredential). The files are made by the very code the server
uses (`pivot_api.sims.build_one`), so they are byte-for-byte what the server would make itself, and
are kept in PIVOT_DATA_DIR/sims (default ./.pivot-data/sims, ignored by git) or --work-dir.

The files carry the SIM_VERSION, a hash of the simulator and analytics source. Change the simulation
rules and the version changes: files uploaded before are never used again. Run generate-upload again
after the rule change is merged (docs/match-data.md).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from pivot_adapters.azure.blob import DEFAULT_CONTAINER, BlobSimStore
from pivot_adapters.local import SimBlob, SimStore
from pivot_api import sims
from pivot_api.sims import SIM_VERSION, SPECS, SimSpec, specs_first


def mb(n: int) -> str:
    return f"{n / 1e6:.1f} MB"


def pick_specs(count: int | None, seeds: list[int] | None) -> list[SimSpec]:
    """`--count N` is the same rule as PIVOT_SIM_MATCHES; `--seeds` picks from that list by seed
    (an unlisted seed gets an even match)."""
    if seeds:
        known = {s.seed: s for s in specs_first(max(len(SPECS), 100))}
        return [known.get(seed) or SimSpec(seed, 70, 70, "4-3-3", "4-4-2") for seed in seeds]
    return specs_first(len(SPECS) if count is None else count)


def banner() -> None:
    print(f"当前模拟器版本 SIM_VERSION = {SIM_VERSION}")
    print("!! 这个版本号由模拟器和统计代码算出来：队友一改模拟规则，它就变，之前上传的文件全部作废。")
    print("!! 规则改完、合并之后，要重新运行 generate-upload。\n")


async def generate_upload(store: SimStore, specs: list[SimSpec], data_dir: Path, force: bool) -> int:
    present = {b.name for b in await store.list()}
    todo, skipped = [], 0
    for spec in specs:
        if not force and all(p.name in present for p in sims.paths(data_dir, spec)):
            skipped += 1
        else:
            todo.append(spec)
    print(f"共 {len(specs)} 场：{skipped} 场云端已有这个版本，跳过；{len(todo)} 场要生成并上传。")
    if not todo:
        return 0
    executor = sims.default_executor(len(todo))
    loop = asyncio.get_running_loop()
    started, total, failed, done = time.monotonic(), 0, 0, 0

    async def one(spec: SimSpec) -> None:
        nonlocal total, failed, done
        try:
            simulated = await loop.run_in_executor(executor, sims.build_one, spec, data_dir, SIM_VERSION)
            if not await sims.push_to_store(store, spec, data_dir):
                raise RuntimeError("upload failed")
            size = sum(p.stat().st_size for p in sims.paths(data_dir, spec))
            total += size
            done += 1
            print(f"[{done}/{len(todo)}] {spec.match_id}  {'生成并上传' if simulated else '本地已有，上传'}  "
                  f"{mb(size)}  已用时 {time.monotonic() - started:.0f}s", flush=True)
        except Exception as exc:
            failed += 1
            done += 1
            print(f"[{done}/{len(todo)}] {spec.match_id}  失败：{exc}", file=sys.stderr, flush=True)

    try:
        await asyncio.gather(*(one(s) for s in todo))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    print(f"\n完成：上传 {len(todo) - failed} 场，共 {mb(total)}，用时 {time.monotonic() - started:.0f}s"
          + (f"；{failed} 场失败，重新运行同一条命令只会补失败的。" if failed else "。"))
    return 1 if failed else 0


def by_version(blobs: list[SimBlob]) -> dict[str, list[SimBlob]]:
    groups: dict[str, list[SimBlob]] = defaultdict(list)
    for b in blobs:
        groups[b.version or "(无法识别)"].append(b)
    return groups


async def list_blobs(store: SimStore) -> int:
    groups = by_version(await store.list())
    if not groups:
        print("云端还没有任何比赛文件。")
    for version, blobs in sorted(groups.items(), key=lambda kv: kv[0] != SIM_VERSION):
        frames = {b.match_id for b in blobs if b.name.endswith(".frames.json.gz")}
        data = {b.match_id for b in blobs if not b.name.endswith(".frames.json.gz")}
        tag = "  <- 当前版本" if version == SIM_VERSION else "  (旧版本，服务器不会用)"
        print(f"{version}{tag}: {len(frames & data)} 场完整，{len(blobs)} 个文件，{mb(sum(b.size for b in blobs))}")
    return 0


async def clean(store: SimStore, delete: bool) -> int:
    old = [b for b in await store.list() if b.version != SIM_VERSION]
    if not old:
        print("没有旧版本的文件，不用清理。")
        return 0
    verb = "删除" if delete else "将会删除（演练，没有真的删）"
    for b in old:
        print(f"  {verb}: {b.name}  {mb(b.size)}")
    print(f"共 {len(old)} 个文件，{mb(sum(b.size for b in old))}；当前版本 {SIM_VERSION} 的文件不动。")
    if not delete:
        print("确定要删，就加上 --yes-delete 再运行一次。")
        return 0
    await store.delete([b.name for b in old])
    print("已删除。")
    return 0


def make_store(args: argparse.Namespace) -> SimStore:
    endpoint = (args.endpoint or os.getenv("PIVOT_BLOB_ENDPOINT") or "").strip()
    if not endpoint:
        sys.exit("没有 Blob 地址：设环境变量 PIVOT_BLOB_ENDPOINT=https://<账号>.blob.core.windows.net/，或用 --endpoint。")
    return BlobSimStore(endpoint, args.container or os.getenv("PIVOT_BLOB_CONTAINER", "").strip() or DEFAULT_CONTAINER)


async def run(args: argparse.Namespace, store: SimStore | None = None) -> int:
    banner()
    store = store or make_store(args)
    try:
        await store.connect()
    except Exception as exc:
        print(f"连不上 Blob：{type(exc).__name__}: {exc}\n（本机要先运行 az login。）", file=sys.stderr)
        return 2
    try:
        if args.cmd == "generate-upload":
            data_dir = Path(args.work_dir) if args.work_dir else sims.data_dir_from_env()
            print(f"文件先生成在 {data_dir}（不会进 git）\n")
            return await generate_upload(store, pick_specs(args.count, args.seeds), data_dir, args.force)
        if args.cmd == "list":
            return await list_blobs(store)
        return await clean(store, args.yes_delete)
    finally:
        await store.close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", help="Blob 地址，默认读 PIVOT_BLOB_ENDPOINT")
    p.add_argument("--container", help="容器名，默认读 PIVOT_BLOB_CONTAINER，再默认 sims")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate-upload", help="生成比赛并上传（云端已有这个版本的会跳过）")
    g.add_argument("--count", type=int, help="场数，规则同 PIVOT_SIM_MATCHES（默认 6）")
    g.add_argument("--seeds", type=lambda s: [int(x) for x in s.split(",") if x], help="指定种子，逗号分隔，例如 101,212")
    g.add_argument("--work-dir", help="生成的文件先放哪，默认 PIVOT_DATA_DIR/sims（.pivot-data/sims）")
    g.add_argument("--force", action="store_true", help="云端已有也重新上传")
    sub.add_parser("list", help="云端有哪些版本、多大")
    c = sub.add_parser("clean", help="删掉不是当前版本的文件（默认只演练）")
    c.add_argument("--yes-delete", action="store_true", help="确认真的删")
    return p


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(asyncio.run(run(parser().parse_args())))
