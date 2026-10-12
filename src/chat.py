import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum

from extraction import (
    CorruptedPdf,
    EncryptedPdf,
    ExtractionError,
    NotAPdf,
    NoText,
    extract,
)

NO_DOCUMENTS = "Upload a PDF first, then ask me about it."

CAPABILITIES_QUESTION = "what can you do?"
CAPABILITIES = """\
I answer questions about your PDFs, using only what's in them.

- **Upload PDFs** with the paperclip button, at any point in the chat.
- **Ask anything** about them. Every answer cites the document and page.
- **Pick a Retrieval mode** in the settings to compare approaches:
  - *Auto* chooses for you, based on how much text there is.
  - *Full context* reads every page.
  - *RAG* searches for the most relevant passages.
  - *Agentic navigation* lets an agent browse outlines and pages.

Scanned pages without a text layer can't be read yet."""


NO_TEXT_LAYER = "(scanned?); OCR isn't supported yet."
REJECTIONS = {
    NotAPdf: "Only PDF files are supported.",
    EncryptedPdf: (
        "The PDF is password-protected. Remove the password and upload it again."
    ),
    CorruptedPdf: "The file is damaged or isn't a valid PDF.",
    NoText: f"No page has a text layer {NO_TEXT_LAYER}",
}


class RetrievalMode(StrEnum):
    AUTO = "Auto"
    FULL_CONTEXT = "Full context"
    RAG = "RAG"
    AGENTIC = "Agentic navigation"


@dataclass(frozen=True)
class Answer:
    text: str


@dataclass(frozen=True)
class Upload:
    name: str
    data: bytes
    mime: str


class Outcome(StrEnum):
    ADDED = "added"
    SKIPPED = "skipped"
    REJECTED = "rejected"


@dataclass(frozen=True)
class FileResult:
    name: str
    outcome: Outcome
    message: str | None = None


@dataclass(frozen=True)
class IngestReport:
    files: list[FileResult]

    @property
    def summary(self) -> str:
        added = self._count(Outcome.ADDED)
        details = []
        if skipped := self._count(Outcome.SKIPPED):
            details.append(f"{skipped} skipped as duplicate")
        if rejected := self._count(Outcome.REJECTED):
            details.append(f"{rejected} rejected")
        summary = f"Added {added} Document{'' if added == 1 else 's'}"
        if details:
            summary += f" ({', '.join(details)})"
        return summary + "."

    def _count(self, outcome: Outcome) -> int:
        return sum(1 for f in self.files if f.outcome == outcome)


class Chat:
    def __init__(self, store):
        self.store = store

    async def ingest(self, thread_id: str, uploads: list[Upload]) -> IngestReport:
        return IngestReport([await self._ingest(thread_id, u) for u in uploads])

    async def _ingest(self, thread_id: str, upload: Upload) -> FileResult:
        if upload.mime != "application/pdf":
            return FileResult(upload.name, Outcome.REJECTED, REJECTIONS[NotAPdf])
        try:
            document = await asyncio.to_thread(extract, upload.data, upload.name)
        except ExtractionError as error:
            return FileResult(upload.name, Outcome.REJECTED, REJECTIONS[type(error)])
        if await self.store.has_document(thread_id, document.content_hash):
            return FileResult(upload.name, Outcome.SKIPPED, "Already in this chat.")
        await self.store.add_document(thread_id, document)
        return FileResult(upload.name, Outcome.ADDED, missing_text_warning(document))

    async def ask(self, thread_id, question, mode, history) -> AsyncIterator[Answer]:
        if question.strip().lower() == CAPABILITIES_QUESTION:
            yield Answer(CAPABILITIES)
            return
        if not await self.store.list_documents(thread_id):
            yield Answer(NO_DOCUMENTS)


def missing_text_warning(document) -> str | None:
    pages = document.pages_without_text
    if not pages:
        return None
    if len(pages) == 1:
        return f"Page {pages[0]} has no text layer {NO_TEXT_LAYER}"
    return f"Pages {page_ranges(pages)} have no text layer {NO_TEXT_LAYER}"


def page_ranges(pages: list[int]) -> str:
    runs = []
    for page in pages:
        if runs and page == runs[-1][-1] + 1:
            runs[-1].append(page)
        else:
            runs.append([page])
    return ", ".join(str(r[0]) if len(r) == 1 else f"{r[0]}–{r[-1]}" for r in runs)
