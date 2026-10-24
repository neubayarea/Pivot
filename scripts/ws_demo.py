"""Watch the local realtime push, drop the connection, reconnect with `since` and see the gap filled.

    uv run python -m pivot_api        # in one terminal (local profile, demo match seeded)
    uv run scripts/ws_demo.py         # in another

Uses the local-only `POST /api/dev/matches/{id}/publish` to push envelopes by hand.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.request

import websockets

DEMO_MATCH_ID = "M-api-demo"


def post(api: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(f"{api}{path}", data=json.dumps(body or {}).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def publish(api: str, match_id: str, minute: int) -> int:
    envelope = post(api, f"/api/dev/matches/{match_id}/publish",
                    {"type": "metric.updated", "payload": {"minute": minute, "momentum": round(0.1 * minute % 1, 2)}})
    return envelope["seq"]


async def receive(ws, n: int) -> list[dict]:
    frames = [json.loads(await asyncio.wait_for(ws.recv(), 5)) for _ in range(n)]
    for f in frames:
        print(f"  <- seq={f['seq']:<3} {f['type']:<15} {f['payload']}")
    return frames


async def main(api: str, match_id: str) -> None:
    url = post(api, f"/api/negotiate?match_id={match_id}")["url"]
    print(f"negotiate -> {url}")

    async with websockets.connect(url) as ws:
        print("connected; publishing 76' and 77'")
        sent = [publish(api, match_id, m) for m in (76, 77)]
        last = (await receive(ws, 2))[-1]["seq"]
        assert last == sent[-1]
    print(f"disconnected at seq={last}; publishing 78', 79', 80' while away")
    missed = [publish(api, match_id, m) for m in (78, 79, 80)]

    async with websockets.connect(f"{url}?since={last}") as ws:
        print(f"reconnected with since={last}; expecting {missed} first")
        assert [f["seq"] for f in await receive(ws, 3)] == missed
        print("caught up; publishing 81' live")
        live = publish(api, match_id, 81)
        assert [f["seq"] for f in await receive(ws, 1)] == [live]
    print("ok: live push, resend after reconnect, nothing duplicated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--match", default=DEMO_MATCH_ID)
    args = parser.parse_args()
    asyncio.run(main(args.api, args.match))
