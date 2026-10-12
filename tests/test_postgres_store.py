import os
import uuid

import pytest
from pdfs import small_pdf

from chunking import Chunk
from extraction import extract
from store import DuplicateDocument, FoundChunk, PostgresStore, connect

pytestmark = pytest.mark.integration


@pytest.fixture
async def pool():
    pool = await connect(os.environ["DATABASE_URL"])
    yield pool
    await pool.close()


@pytest.fixture
def thread_id():
    return str(uuid.uuid4())


async def test_stores_documents_per_thread_and_deletes_them_with_the_thread(
    pool, thread_id
):
    store = PostgresStore(pool)
    document = extract(small_pdf(), "invoice.pdf")
    chunks = [Chunk("Total due", 1, 1), Chunk("Late fees", 1, 2)]
    embeddings = [[1.0] + [0.0] * 383, [0.0, 1.0] + [0.0] * 382]

    document_id = await store.add_document(thread_id, document, chunks, embeddings)

    assert await store.has_document(thread_id, document.content_hash)
    assert not await store.has_document(str(uuid.uuid4()), document.content_hash)
    [info] = await store.list_documents(thread_id)
    assert (info.id, info.name, info.page_count) == (document_id, "invoice.pdf", 2)

    query = [0.1, 0.9] + [0.0] * 382
    assert await store.search(thread_id, query, limit=1) == [
        FoundChunk("invoice.pdf", Chunk("Late fees", 1, 2))
    ]
    assert await store.search(str(uuid.uuid4()), query, limit=1) == []

    with pytest.raises(DuplicateDocument):
        await store.add_document(thread_id, document, chunks, embeddings)

    await pool.execute('DELETE FROM "Thread" WHERE id = $1', thread_id)
    assert await store.list_documents(thread_id) == []
    assert await store.search(thread_id, query, limit=1) == []
