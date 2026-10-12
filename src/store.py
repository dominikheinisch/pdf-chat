import json
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass

import asyncpg
from pgvector.asyncpg import register_vector

from chunking import Chunk
from extraction import Document, OutlineEntry


@dataclass(frozen=True)
class DocumentInfo:
    id: str
    name: str
    page_count: int
    tokens: int


@dataclass(frozen=True)
class StoredDocument:
    id: str
    name: str
    pages: list[str]


@dataclass(frozen=True)
class FoundChunk:
    document: str
    chunk: Chunk


class DuplicateDocument(Exception):
    pass


class MemoryStore:
    def __init__(self):
        self._documents = defaultdict(dict)
        self._chunks = defaultdict(list)

    async def add_document(
        self,
        thread_id: str,
        document: Document,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> str:
        if await self.has_document(thread_id, document.content_hash):
            raise DuplicateDocument(document.name)
        document_id = str(uuid.uuid4())
        self._documents[thread_id][document_id] = document
        for c, embedding in zip(chunks, embeddings, strict=True):
            self._chunks[thread_id].append((FoundChunk(document.name, c), embedding))
        return document_id

    async def get_outline(self, thread_id: str, document_id: str) -> list[OutlineEntry]:
        return self._documents[thread_id][document_id].outline

    async def read_pages(
        self, thread_id: str, document_id: str, first: int, last: int
    ) -> list[str]:
        return self._documents[thread_id][document_id].pages[first - 1 : last]

    async def search(
        self, thread_id: str, embedding: list[float], limit: int
    ) -> list[FoundChunk]:
        ranked = sorted(
            self._chunks[thread_id],
            key=lambda item: cosine_distance(item[1], embedding),
        )
        return [found for found, _ in ranked[:limit]]

    async def has_document(self, thread_id: str, content_hash: str) -> bool:
        return any(
            d.content_hash == content_hash for d in self._documents[thread_id].values()
        )

    async def list_documents(self, thread_id: str) -> list[DocumentInfo]:
        return [
            DocumentInfo(id, d.name, len(d.pages), d.tokens)
            for id, d in self._documents[thread_id].items()
        ]

    async def load_documents(self, thread_id: str) -> list[StoredDocument]:
        return [
            StoredDocument(id, d.name, d.pages)
            for id, d in self._documents[thread_id].items()
        ]


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norms = sum(x * x for x in a) ** 0.5 * sum(y * y for y in b) ** 0.5
    return 1 - dot / norms if norms else 1.0


async def connect(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, init=register_vector)


class PostgresStore:
    def __init__(self, pool):
        self.pool = pool

    async def add_document(
        self,
        thread_id: str,
        document: Document,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> str:
        outline = json.dumps([asdict(entry) for entry in document.outline])
        async with self.pool.acquire() as connection, connection.transaction():
            # Uploads can arrive before Chainlit has saved the Thread.
            await connection.execute(
                """INSERT INTO "Thread" (id, metadata) VALUES ($1, '{}')
                   ON CONFLICT (id) DO NOTHING""",
                thread_id,
            )
            try:
                document_id = await connection.fetchval(
                    """INSERT INTO documents
                           (thread_id, name, content_hash, pages, outline, tokens)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       RETURNING id""",
                    thread_id,
                    document.name,
                    document.content_hash,
                    document.pages,
                    outline,
                    document.tokens,
                )
            except asyncpg.UniqueViolationError as error:
                raise DuplicateDocument(document.name) from error
            await connection.executemany(
                """INSERT INTO chunks
                       (document_id, position, text, page_start, page_end, embedding)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                [
                    (document_id, position, c.text, c.page_start, c.page_end, embedding)
                    for position, (c, embedding) in enumerate(zip(chunks, embeddings))
                ],
            )
        return document_id

    async def search(
        self, thread_id: str, embedding: list[float], limit: int
    ) -> list[FoundChunk]:
        rows = await self.pool.fetch(
            """SELECT d.name, c.text, c.page_start, c.page_end
               FROM chunks c JOIN documents d ON d.id = c.document_id
               WHERE d.thread_id = $1
               ORDER BY c.embedding <=> $2
               LIMIT $3""",
            thread_id,
            embedding,
            limit,
        )
        return [
            FoundChunk(
                row["name"], Chunk(row["text"], row["page_start"], row["page_end"])
            )
            for row in rows
        ]

    async def has_document(self, thread_id: str, content_hash: str) -> bool:
        return await self.pool.fetchval(
            """SELECT EXISTS (
                   SELECT 1 FROM documents WHERE thread_id = $1 AND content_hash = $2
               )""",
            thread_id,
            content_hash,
        )

    async def list_documents(self, thread_id: str) -> list[DocumentInfo]:
        rows = await self.pool.fetch(
            """SELECT id, name, cardinality(pages) AS page_count, tokens
               FROM documents WHERE thread_id = $1 ORDER BY created_at""",
            thread_id,
        )
        return [DocumentInfo(**row) for row in rows]

    async def load_documents(self, thread_id: str) -> list[StoredDocument]:
        rows = await self.pool.fetch(
            """SELECT id, name, pages FROM documents
               WHERE thread_id = $1 ORDER BY created_at""",
            thread_id,
        )
        return [StoredDocument(**row) for row in rows]

    async def get_outline(self, thread_id: str, document_id: str) -> list[OutlineEntry]:
        outline = await self.pool.fetchval(
            "SELECT outline FROM documents WHERE thread_id = $1 AND id = $2",
            thread_id,
            document_id,
        )
        return [OutlineEntry(**entry) for entry in json.loads(outline)]

    async def read_pages(
        self, thread_id: str, document_id: str, first: int, last: int
    ) -> list[str]:
        return await self.pool.fetchval(
            "SELECT pages[$3:$4] FROM documents WHERE thread_id = $1 AND id = $2",
            thread_id,
            document_id,
            first,
            last,
        )
