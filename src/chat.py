import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum

from langchain_core.messages import HumanMessage

from agent import MAX_TOOL_CALLS, STOPPED_EARLY, build_agent, make_tools
from answers import (
    Answer,
    Location,
    Sources,
    document_block,
    page_label,
    recent,
    stream_answer,
)
from chunking import chunk
from citations import CitationNumbering
from extraction import (
    CorruptedPdf,
    EncryptedPdf,
    ExtractionError,
    NotAPdf,
    NoText,
    extract,
)

TOP_CHUNKS = 8
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
class ModeUsed:
    label: str


@dataclass(frozen=True)
class ToolUsed:
    name: str
    input: dict
    output: str


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

    @property
    def quick_replies(self) -> list[str]:
        added = [f.name for f in self.files if f.outcome == Outcome.ADDED]
        if len(added) == 1:
            return [f"Summarize {added[0]}", f"Key points of {added[0]}"]
        if added:
            return ["Summarize the new documents", "Compare them"]
        return []

    def _count(self, outcome: Outcome) -> int:
        return sum(1 for f in self.files if f.outcome == outcome)


class Chat:
    def __init__(self, store, embedder, llm=None, model=None, chat_model=None):
        self.store = store
        self.embedder = embedder
        self.llm = llm
        self.model = model
        self.chat_model = chat_model

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
        chunks = await asyncio.to_thread(chunk, document.pages)
        embeddings = await self.embedder.embed_passages([c.text for c in chunks])
        await self.store.add_document(thread_id, document, chunks, embeddings)
        return FileResult(upload.name, Outcome.ADDED, missing_text_warning(document))

    async def ask(
        self, thread_id, question, mode, history
    ) -> AsyncIterator[Answer | ModeUsed | Sources]:
        if question.strip().lower() == CAPABILITIES_QUESTION:
            yield Answer(CAPABILITIES)
            return
        documents = await self.store.load_documents(thread_id)
        if not documents:
            yield Answer(NO_DOCUMENTS)
            return
        if mode == RetrievalMode.RAG:
            answer = self._rag(thread_id, question, history)
        elif mode == RetrievalMode.AGENTIC:
            answer = self._agentic(thread_id, question, history)
        else:
            answer = self._full_context(documents, question, history)
        async for event in answer:
            yield event

    async def _full_context(self, documents, question, history):
        yield ModeUsed(RetrievalMode.FULL_CONTEXT)

        def locate(citation) -> Location:
            document = documents[citation.document_index]
            return Location(
                document.name, citation.start_block_index + 1, citation.end_block_index
            )

        blocks = [document_block(d.name, d.pages) for d in documents]
        async for event in stream_answer(
            self.llm, self.model, blocks, question, history, locate
        ):
            yield event

    async def _rag(self, thread_id, question, history):
        yield ModeUsed(RetrievalMode.RAG)
        query = await self.embedder.embed_query(question)
        found = await self.store.search(thread_id, query, TOP_CHUNKS)

        def locate(citation) -> Location:
            hit = found[citation.document_index]
            return Location(hit.document, hit.chunk.page_start, hit.chunk.page_end)

        blocks = [
            document_block(
                page_label(f.document, f.chunk.page_start, f.chunk.page_end),
                [f.chunk.text],
            )
            for f in found
        ]
        async for event in stream_answer(
            self.llm, self.model, blocks, question, history, locate
        ):
            yield event

    async def _agentic(self, thread_id, question, history):
        yield ModeUsed(RetrievalMode.AGENTIC)
        tools = make_tools(self.store, self.embedder, thread_id)
        graph = build_agent(self.chat_model, tools)
        state = {
            "messages": [*recent(history), HumanMessage(question)],
            "tool_calls": 0,
        }
        numbering = CitationNumbering()
        tool_calls = 0
        # The limit is a safety net; the agent itself stops after MAX_TOOL_CALLS.
        config = {"recursion_limit": 4 * MAX_TOOL_CALLS}
        async for event in graph.astream_events(state, config, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                if text := numbering.feed(event["data"]["chunk"].text):
                    yield Answer(text)
            elif kind == "on_tool_end":
                tool_calls += 1
                output = event["data"]["output"]
                yield ToolUsed(
                    event["name"],
                    event["data"].get("input", {}),
                    str(getattr(output, "content", output)),
                )
        if text := numbering.flush():
            yield Answer(text)
        if tool_calls >= MAX_TOOL_CALLS:
            yield Answer(STOPPED_EARLY)
        yield Sources(numbering.sources)


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
