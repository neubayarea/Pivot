"""Profile L smoke test: publish an event -> consume -> store -> subscriber receives the broadcast."""

import asyncio

from pivot_adapters import build_adapters
from pivot_core.domain import Envelope, MatchEvent

QUEUE = "match-events"


async def consume_one(adapters) -> None:
    msg = await adapters.queue.receive(QUEUE, timeout=1)
    event = MatchEvent.model_validate(msg.body)
    await adapters.matches.append_events([event])
    await adapters.live.publish(Envelope(
        type="event.batch", match_id=event.match_id, seq=event.seq, ts="2026-10-23T20:00:00Z",
        payload={"events": [event.model_dump(mode="json")]},   # browsers get computed fields too
    ))
    await adapters.queue.complete(msg)


def test_event_flows_through_profile_l(make_event):
    async def run():
        adapters = build_adapters("local")
        event = make_event(7)
        async with adapters.live.subscribe("m1") as sub:
            await adapters.queue.send(QUEUE, event.event_id, event.model_dump(mode="json", round_trip=True))
            await consume_one(adapters)
            envelope = await sub.get(timeout=1)

        assert envelope.type == "event.batch"
        assert envelope.payload["events"][0]["event_id"] == event.event_id
        assert await adapters.matches.list_events("m1") == [event]
        assert await adapters.queue.receive(QUEUE, timeout=0.01) is None
    asyncio.run(run())
