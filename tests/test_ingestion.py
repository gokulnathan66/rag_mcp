import asyncio
from app.orchestrator import Orchestrator


async def test_ingest_collection():
    orch = Orchestrator()
    res = await orch.ingest_collection("test_collection")
    assert res["status"] == "ok"
    assert res["collection"] == "test_collection"


def test_sync_ingest():
    # run async test
    asyncio.run(test_ingest_collection())
