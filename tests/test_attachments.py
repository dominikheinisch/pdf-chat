import chainlit as cl
import pytest
from chainlit.auth import get_current_user
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from attachments import AttachmentStore

KEY = "threads/thread-1/files/element-1"


@pytest.fixture
def store(tmp_path):
    return AttachmentStore(tmp_path / "files")


def client_for(store, logged_in=True):
    app = FastAPI()
    app.include_router(store.router)
    if logged_in:
        app.dependency_overrides[get_current_user] = lambda: cl.User(identifier="demo")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_serves_an_uploaded_attachment_back_with_its_type(store):
    await store.upload_file(KEY, b"%PDF-1.7 bytes", mime="application/pdf")

    async with client_for(store) as client:
        response = await client.get(await store.get_read_url(KEY))

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 bytes"
    assert response.headers["content-type"] == "application/pdf"


async def test_opens_pdfs_in_the_browser_and_downloads_other_files(store):
    pdf, text = KEY, "threads/thread-1/files/element-2"
    await store.upload_file(
        pdf,
        b"%PDF",
        mime="application/pdf",
        content_disposition='attachment; filename="invoice.pdf"',
    )
    await store.upload_file(
        text,
        "**invoice.pdf, p. 1**",
        mime="text/plain",
        content_disposition='attachment; filename="Source 1"',
    )

    async with client_for(store) as client:
        pdf_response = await client.get(await store.get_read_url(pdf))
        text_response = await client.get(await store.get_read_url(text))

    assert (
        pdf_response.headers["content-disposition"] == 'inline; filename="invoice.pdf"'
    )
    assert text_response.headers["content-disposition"] == (
        'attachment; filename="Source 1"'
    )
    assert text_response.text == "**invoice.pdf, p. 1**"


async def test_answers_not_found_for_an_unknown_attachment(store):
    async with client_for(store) as client:
        response = await client.get(await store.get_read_url(KEY))

    assert response.status_code == 404


async def test_a_deleted_attachment_is_gone(store):
    await store.upload_file(KEY, b"%PDF", mime="application/pdf")

    assert await store.delete_file(KEY)

    async with client_for(store) as client:
        response = await client.get(await store.get_read_url(KEY))
    assert response.status_code == 404


async def test_refuses_keys_that_point_outside_the_attachments_directory(
    store, tmp_path
):
    (tmp_path / "secret").write_text("not an attachment")
    (tmp_path / "secret.json").write_text('{"mime": "text/plain"}')
    await store.upload_file(KEY, b"%PDF", mime="application/pdf")

    with pytest.raises(ValueError):
        await store.upload_file("../secret", b"overwritten")

    async with client_for(store) as client:
        # Encoded so the client sends the dot segment instead of resolving it.
        response = await client.get("/attachments/%2E%2E/secret")
    assert response.status_code == 404
    assert (tmp_path / "secret").read_text() == "not an attachment"


async def test_requires_a_logged_in_user(store):
    await store.upload_file(KEY, b"%PDF", mime="application/pdf")

    async with client_for(store, logged_in=False) as client:
        response = await client.get(await store.get_read_url(KEY))

    assert response.status_code == 401


async def test_only_pdfs_open_in_the_browser_whatever_chainlit_asks_for(store):
    await store.upload_file(
        KEY, b"<html>", mime="text/html", content_disposition='inline; filename="x"'
    )

    async with client_for(store) as client:
        response = await client.get(await store.get_read_url(KEY))

    assert response.headers["content-disposition"] == 'attachment; filename="x"'


async def test_answers_not_found_for_a_key_that_is_not_an_attachment(store):
    await store.upload_file(KEY, b"%PDF", mime="application/pdf")

    async with client_for(store) as client:
        response = await client.get(await store.get_read_url(KEY) + ".json")

    assert response.status_code == 404
