import hashlib
from dataclasses import dataclass, field

import pymupdf

# Fallback outline titles are cut to this length.
MAX_TITLE = 80


class ExtractionError(Exception):
    pass


class NotAPdf(ExtractionError):
    pass


class EncryptedPdf(ExtractionError):
    pass


class CorruptedPdf(ExtractionError):
    pass


class NoText(ExtractionError):
    pass


@dataclass(frozen=True)
class OutlineEntry:
    level: int
    title: str
    page: int


@dataclass(frozen=True)
class Document:
    name: str
    content_hash: str
    pages: list[str]
    outline: list[OutlineEntry] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return estimate_tokens("".join(self.pages))

    @property
    def pages_without_text(self) -> list[int]:
        return [number for number, text in enumerate(self.pages, start=1) if not text]


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def extract(data: bytes, name: str) -> Document:
    # The header may follow some junk bytes, but must be near the start.
    if b"%PDF-" not in data[:1024]:
        raise NotAPdf(name)
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except pymupdf.FileDataError as error:
        raise CorruptedPdf(name) from error
    with pdf:
        if pdf.needs_pass:
            raise EncryptedPdf(name)
        if pdf.page_count == 0:
            raise CorruptedPdf(name)
        pages = [page.get_text().strip() for page in pdf]
        bookmarks = pdf.get_toc(simple=True)
    if not any(pages):
        raise NoText(name)
    outline = [OutlineEntry(level, title, page) for level, title, page in bookmarks]
    return Document(
        name=name,
        content_hash=hashlib.sha256(data).hexdigest(),
        pages=pages,
        outline=outline or first_lines(pages),
    )


def first_lines(pages: list[str]) -> list[OutlineEntry]:
    return [
        OutlineEntry(level=1, title=text.splitlines()[0][:MAX_TITLE], page=number)
        for number, text in enumerate(pages, start=1)
        if text
    ]
