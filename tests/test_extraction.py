import pytest
from pdfs import make_pdf, small_pdf

from extraction import (
    CorruptedPdf,
    EncryptedPdf,
    NotAPdf,
    NoText,
    OutlineEntry,
    extract,
)


def test_reads_the_text_of_every_page():
    document = extract(small_pdf(), "invoice.pdf")

    assert document.name == "invoice.pdf"
    assert len(document.pages) == 2
    assert "Total due: 1,250 EUR" in document.pages[0]
    assert "2% interest" in document.pages[1]


def test_lists_the_pages_without_a_text_layer():
    pdf = make_pdf(["Intro", "scan", "scan", "Appendix"], image_pages={2, 3})

    document = extract(pdf, "mixed.pdf")

    assert document.pages_without_text == [2, 3]
    assert document.pages[1] == ""


def test_takes_the_outline_from_the_bookmarks():
    pdf = make_pdf(
        ["Cover", "Scope of work", "Payment"],
        outline=[(1, "Contract", 1), (2, "Scope", 2), (2, "Payment", 3)],
    )

    document = extract(pdf, "contract.pdf")

    assert document.outline == [
        OutlineEntry(level=1, title="Contract", page=1),
        OutlineEntry(level=2, title="Scope", page=2),
        OutlineEntry(level=2, title="Payment", page=3),
    ]


def test_builds_an_outline_from_first_lines_when_there_are_no_bookmarks():
    pdf = make_pdf(
        ["Invoice 2024-17\nTotal due", "scan", "Payment terms\nLate fees"],
        image_pages={2},
    )

    document = extract(pdf, "invoice.pdf")

    assert document.outline == [
        OutlineEntry(level=1, title="Invoice 2024-17", page=1),
        OutlineEntry(level=1, title="Payment terms", page=3),
    ]


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (b"just some text", NotAPdf),
        (b"%PDF-1.7\n1 0 obj << /Type /Catalog >> broken", CorruptedPdf),
        (make_pdf(["secret"], password="hunter2"), EncryptedPdf),
        (make_pdf(["scan", "scan"], image_pages={1, 2}), NoText),
    ],
)
def test_refuses_files_it_cannot_read(data, error):
    with pytest.raises(error):
        extract(data, "bad.pdf")


def test_identifies_a_pdf_by_its_content():
    pdf = small_pdf()
    first = extract(pdf, "invoice.pdf")
    renamed = extract(pdf, "copy of invoice.pdf")
    other = extract(make_pdf(["Something else"]), "other.pdf")

    assert first.content_hash == renamed.content_hash
    assert first.content_hash != other.content_hash
