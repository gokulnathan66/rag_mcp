# Embedder stub (uses dummy vectors)


class Embedder:
    def __init__(self, model_name: str = None, batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size

    async def embed_texts(self, texts: list) -> list:
        # create deterministic dummy vectors for now
        return [[float(len(t)) for _ in range(8)] for t in texts]

    async def embed_query(self, text: str) -> list:
        vec = [float(len(text)) for _ in range(8)]
        return vec
