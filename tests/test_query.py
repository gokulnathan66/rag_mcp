import asyncio
from app.orchestrator import Orchestrator


async def test_query():
    orch = Orchestrator()
    res = await orch.query("hello world")
    assert isinstance(res, list)


def test_sync_query():
    asyncio.run(test_query())
