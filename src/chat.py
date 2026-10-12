from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum

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


class RetrievalMode(StrEnum):
    AUTO = "Auto"
    FULL_CONTEXT = "Full context"
    RAG = "RAG"
    AGENTIC = "Agentic navigation"


@dataclass(frozen=True)
class Answer:
    text: str


class Chat:
    def __init__(self, store):
        self.store = store

    async def ask(self, thread_id, question, mode, history) -> AsyncIterator[Answer]:
        if question.strip().lower() == CAPABILITIES_QUESTION:
            yield Answer(CAPABILITIES)
            return
        if not await self.store.list_documents(thread_id):
            yield Answer(NO_DOCUMENTS)
