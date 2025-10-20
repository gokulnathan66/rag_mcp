# Qdrant client stub


class QdrantClient:
    def __init__(self, url: str = "http://localhost:6333", api_key: str = None):
        self.url = url
        self.api_key = api_key

    async def upsert_points(self, collection_name: str, points: list):
        # stub: would call qdrant client to upsert points
        return {"status": "ok", "count": len(points)}

    async def search(self, collection_name: str, vector: list, top_k: int = 10):
        return []

    async def delete_point(self, collection_name: str, point_id: str):
        return {"status": "ok"}
