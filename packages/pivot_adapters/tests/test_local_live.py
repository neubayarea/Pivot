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


def test_seq_stays_increasing_across_publishers(make_envelope):
    async def run():
        live = InMemoryLivePublisher()
        async with live.subscribe("m1") as sub:
            for seq in (1, 2, 1, 5, 3):           # two publishers counting on their own
                await live.publish(make_envelope(seq))
            assert [(await sub.get(1)).seq for _ in range(5)] == [1, 2, 3, 5, 6]
        assert live.last_seq("m1") == 6 and live.last_seq("m2") == -1
    asyncio.run(run())


def test_replay_returns_what_came_after_since(make_envelope):
    async def run():
        live = InMemoryLivePublisher(history=3)
        for seq in range(1, 6):
            await live.publish(make_envelope(seq))
        assert [e.seq for e in live.replay("m1", 3)] == [4, 5]
        assert [e.seq for e in live.replay("m1")] == [3, 4, 5]   # 1 and 2 were evicted
        assert live.replay("m2") == []
    asyncio.run(run())
