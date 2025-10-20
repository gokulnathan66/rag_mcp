from typing import List

# Minimal LangGraph-like orchestrator stub


class Orchestrator:
    def __init__(self, config=None):
        self.config = config

    async def ingest_collection(self, collection_name: str, filters: dict = None) -> dict:
        # stub: would call Firestore client, chunk, embed and write to Qdrant
        return {"status": "ok", "collection": collection_name}

    async def query(self, query_text: str, max_results: int = 10) -> List[dict]:
        # stub: would create embedding and query Qdrant
        return []
