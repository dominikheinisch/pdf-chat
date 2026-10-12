import json
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass

import asyncpg

from extraction import Document


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


class DuplicateDocument(Exception):
    pass


class MemoryStore:
    def __init__(self):
        self._documents = defaultdict(dict)

    async def add_document(self, thread_id: str, document: Document) -> str:
        if await self.has_document(thread_id, document.content_hash):
            raise DuplicateDocument(document.name)
        document_id = str(uuid.uuid4())
        self._documents[thread_id][document_id] = document
        return document_id

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


class PostgresStore:
    def __init__(self, pool):
        self.pool = pool

    async def add_document(self, thread_id: str, document: Document) -> str:
        outline = json.dumps([asdict(entry) for entry in document.outline])
        async with self.pool.acquire() as connection, connection.transaction():
            # Uploads can arrive before Chainlit has saved the Thread.
            await connection.execute(
                """INSERT INTO "Thread" (id, metadata) VALUES ($1, '{}')
                   ON CONFLICT (id) DO NOTHING""",
                thread_id,
            )
            try:
                return await connection.fetchval(
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
