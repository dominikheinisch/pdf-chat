from pdfs import make_pdf, small_pdf

from chat import Chat, Outcome, Upload
from store import MemoryStore

PDF = "application/pdf"


async def ingest(chat, *uploads, thread_id="thread-1"):
    return await chat.ingest(thread_id, list(uploads))


async def test_adds_a_pdf_to_the_thread():
    chat = Chat(store=MemoryStore())

    report = await ingest(chat, Upload("invoice.pdf", small_pdf(), PDF))

    assert [(f.name, f.outcome) for f in report.files] == [
        ("invoice.pdf", Outcome.ADDED)
    ]
    assert report.summary == "Added 1 Document."


async def test_skips_a_pdf_that_is_already_in_the_thread():
    chat = Chat(store=MemoryStore())
    pdf = small_pdf()
    await ingest(chat, Upload("invoice.pdf", pdf, PDF))

    report = await ingest(chat, Upload("invoice (1).pdf", pdf, PDF))

    assert report.files[0].outcome == Outcome.SKIPPED
    assert report.files[0].message == "Already in this chat."
    assert report.summary == "Added 0 Documents (1 skipped as duplicate)."


async def test_the_same_pdf_can_be_added_to_another_thread():
    chat = Chat(store=MemoryStore())
    pdf = small_pdf()
    await ingest(chat, Upload("invoice.pdf", pdf, PDF), thread_id="thread-1")

    report = await ingest(chat, Upload("invoice.pdf", pdf, PDF), thread_id="thread-2")

    assert report.files[0].outcome == Outcome.ADDED


async def test_reports_each_file_of_a_mixed_upload():
    chat = Chat(store=MemoryStore())
    pdf = small_pdf()

    report = await ingest(
        chat,
        Upload("invoice.pdf", pdf, PDF),
        Upload("again.pdf", pdf, PDF),
        Upload("notes.txt", b"hello", "text/plain"),
        Upload("locked.pdf", make_pdf(["secret"], password="pw"), PDF),
        Upload("broken.pdf", b"%PDF-1.7 broken", PDF),
        Upload("scan.pdf", make_pdf(["x"], image_pages={1}), PDF),
    )

    assert [(f.name, f.outcome, f.message) for f in report.files] == [
        ("invoice.pdf", Outcome.ADDED, None),
        ("again.pdf", Outcome.SKIPPED, "Already in this chat."),
        ("notes.txt", Outcome.REJECTED, "Only PDF files are supported."),
        (
            "locked.pdf",
            Outcome.REJECTED,
            "The PDF is password-protected. Remove the password and upload it again.",
        ),
        ("broken.pdf", Outcome.REJECTED, "The file is damaged or isn't a valid PDF."),
        (
            "scan.pdf",
            Outcome.REJECTED,
            "No page has a text layer (scanned?); OCR isn't supported yet.",
        ),
    ]
    assert report.summary == "Added 1 Document (1 skipped as duplicate, 4 rejected)."


async def test_warns_about_pages_without_a_text_layer():
    chat = Chat(store=MemoryStore())
    pdf = make_pdf(["a", "b", "c", "d", "e", "f"], image_pages={2, 3, 4, 6})

    report = await ingest(chat, Upload("mixed.pdf", pdf, PDF))

    assert report.files[0].outcome == Outcome.ADDED
    assert report.files[0].message == (
        "Pages 2–4, 6 have no text layer (scanned?); OCR isn't supported yet."
    )


async def test_warns_about_a_single_page_without_a_text_layer():
    chat = Chat(store=MemoryStore())
    pdf = make_pdf(["a", "b"], image_pages={2})

    report = await ingest(chat, Upload("mixed.pdf", pdf, PDF))

    assert report.files[0].message == (
        "Page 2 has no text layer (scanned?); OCR isn't supported yet."
    )
