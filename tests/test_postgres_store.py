import os
import uuid

import asyncpg
import pytest
from pdfs import small_pdf

from extraction import extract
from store import DuplicateDocument, PostgresStore

pytestmark = pytest.mark.integration


@pytest.fixture
async def pool():
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
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

    document_id = await store.add_document(thread_id, document)

    assert await store.has_document(thread_id, document.content_hash)
    assert not await store.has_document(str(uuid.uuid4()), document.content_hash)
    [info] = await store.list_documents(thread_id)
    assert (info.id, info.name, info.page_count) == (document_id, "invoice.pdf", 2)

    with pytest.raises(DuplicateDocument):
        await store.add_document(thread_id, document)

    await pool.execute('DELETE FROM "Thread" WHERE id = $1', thread_id)
    assert await store.list_documents(thread_id) == []
