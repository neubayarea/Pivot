import asyncio

import pytest

from pivot_adapters.local import InMemoryLivePublisher


def test_broadcast_reaches_only_that_match(make_envelope):
    async def run():
        live = InMemoryLivePublisher()
        async with live.subscribe("m1") as a, live.subscribe("m1") as b, live.subscribe("m2") as other:
            await live.publish(make_envelope(1))
            await live.publish(make_envelope(2))
            for sub in (a, b):
                assert [(await sub.get(1)).seq, (await sub.get(1)).seq] == [1, 2]
            with pytest.raises(TimeoutError):
                await other.get(0.01)
    asyncio.run(run())


def test_unsubscribe_on_exit(make_envelope):
    async def run():
        live = InMemoryLivePublisher()
        async with live.subscribe("m1"):
            assert live.subscriber_count("m1") == 1
        assert live.subscriber_count("m1") == 0
        await live.publish(make_envelope(1))   # no subscribers: no error
    asyncio.run(run())


def test_slow_subscriber_drops_overflow(make_envelope):
    async def run():
        live = InMemoryLivePublisher(maxsize=2)
        async with live.subscribe("m1") as sub:
            for seq in range(5):
                await live.publish(make_envelope(seq))
            assert sub.dropped == 3
            assert [(await sub.get(1)).seq for _ in range(2)] == [0, 1]
    asyncio.run(run())
