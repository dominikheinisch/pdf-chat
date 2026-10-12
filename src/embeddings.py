import asyncio

from fastembed import TextEmbedding

# Small and English-only; downloaded into the image at build time (see Dockerfile).
MODEL = "BAAI/bge-small-en-v1.5"


class FastEmbedder:
    def __init__(self):
        self.model = TextEmbedding(MODEL)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        vectors = await asyncio.to_thread(lambda: list(self.model.passage_embed(texts)))
        return [v.tolist() for v in vectors]

    async def embed_query(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(lambda: list(self.model.query_embed(text)))
        return vectors[0].tolist()
