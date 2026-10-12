"""Builds test PDFs in code, so no binary fixtures are committed."""

import pymupdf


def make_pdf(pages, outline=(), image_pages=(), password=None):
    doc = pymupdf.open()
    for number, text in enumerate(pages, start=1):
        page = doc.new_page()
        if number in image_pages:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
            pixmap.set_rect(pixmap.irect, (120, 120, 120))
            page.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pixmap)
        else:
            page.insert_textbox(pymupdf.Rect(72, 72, 540, 770), text, fontsize=9)
    if outline:
        doc.set_toc([list(entry) for entry in outline])
    options = {}
    if password:
        options = {
            "encryption": pymupdf.PDF_ENCRYPT_AES_256,
            "user_pw": password,
            "owner_pw": password,
        }
    return doc.tobytes(**options)


def paragraph(topic, sentences=8):
    return " ".join(
        f"Sentence {n} about {topic} explains one more detail of it."
        for n in range(sentences)
    )


def small_pdf():
    return make_pdf(
        [
            "Invoice 2024-17\n\nTotal due: 1,250 EUR by 30 June.",
            "Payment terms\n\nLate payments add 2% interest per month.",
        ]
    )


def large_pdf(pages=120):
    return make_pdf(
        [
            "\n\n".join(paragraph(f"topic {page}-{block}") for block in range(4))
            for page in range(1, pages + 1)
        ]
    )
