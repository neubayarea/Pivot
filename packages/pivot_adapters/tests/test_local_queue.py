import asyncio

import pytest

from pivot_adapters.local import InMemoryWorkQueue
from pivot_core.ports import PIVOT_CANDIDATES


def test_send_receive_complete():
    async def run():
        q = InMemoryWorkQueue()
        await q.send(PIVOT_CANDIDATES, "m1:55", {"minute": 55})
        msg = await q.receive(PIVOT_CANDIDATES, timeout=1)
        assert (msg.message_id, msg.body, msg.delivery_count) == ("m1:55", {"minute": 55}, 1)
        await q.complete(msg)
        assert await q.receive(PIVOT_CANDIDATES, timeout=0.01) is None
        with pytest.raises(ValueError):
            await q.complete(msg)
    asyncio.run(run())


def test_duplicate_message_id_is_dropped():
    async def run():
        q = InMemoryWorkQueue()
        await q.send("q", "a", {"n": 1})
        await q.send("q", "a", {"n": 2})
        assert (await q.receive("q", timeout=1)).body == {"n": 1}
        assert await q.receive("q", timeout=0.01) is None
    asyncio.run(run())


def test_abandon_redelivers():
    async def run():
        q = InMemoryWorkQueue()
        await q.send("q", "a", {})
        first = await q.receive("q", timeout=1)
        await q.abandon(first)
        again = await q.receive("q", timeout=1)
        assert again.message_id == "a" and again.delivery_count == 2
    asyncio.run(run())


def test_queues_are_separate_and_receive_waits():
    async def run():
        q = InMemoryWorkQueue()
        waiter = asyncio.create_task(q.receive("b", timeout=1))
        await q.send("a", "x", {})
        await q.send("b", "y", {})
        assert (await waiter).message_id == "y"
        assert (await q.receive("a", timeout=1)).message_id == "x"
    asyncio.run(run())


def test_renew_lock_and_dead_letter():
    async def run():
        q = InMemoryWorkQueue()
        await q.send("q", "a", {"n": 1})
        msg = await q.receive("q", timeout=1)
        await q.renew_lock(msg)
        await q.dead_letter(msg, "boom")
        assert [(m.message_id, why) for m, why in q.dead_letters["q"]] == [("a", "boom")]
        assert await q.receive("q", timeout=0.01) is None
        with pytest.raises(ValueError):
            await q.renew_lock(msg)
    asyncio.run(run())
