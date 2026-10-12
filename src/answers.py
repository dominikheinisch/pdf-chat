from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

SYSTEM_PROMPT = """\
You answer questions about the user's documents. Use only the documents provided; \
never fall back on general knowledge. If the documents don't contain the answer, \
say so plainly. Cite the passages that support each claim. Be concise."""

MAX_TOKENS = 4096
HISTORY_TURNS = 10
NO_TEXT_LAYER = "[This page has no text layer.]"


@dataclass(frozen=True)
class Answer:
    text: str


@dataclass(frozen=True)
class Source:
    number: int
    document: str
    page_start: int
    page_end: int
    quote: str

    @property
    def label(self) -> str:
        return page_label(self.document, self.page_start, self.page_end)


@dataclass(frozen=True)
class Sources:
    sources: list[Source]


@dataclass(frozen=True)
class Location:
    document: str
    page_start: int
    page_end: int


def page_label(document: str, first: int, last: int) -> str:
    if first == last:
        return f"{document}, p. {first}"
    return f"{document}, pp. {first}–{last}"


def recent(history: list[dict]) -> list[dict]:
    messages = [m for m in history if m["content"].strip()][-2 * HISTORY_TURNS :]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def document_block(title: str, passages: list[str]) -> dict:
    return {
        "type": "document",
        "source": {
            "type": "content",
            "content": [{"type": "text", "text": p or NO_TEXT_LAYER} for p in passages],
        },
        "title": title,
        "citations": {"enabled": True},
    }


async def stream_answer(
    llm,
    model: str,
    documents: list[dict],
    question: str,
    history: list[dict],
    locate: Callable[[object], Location],
) -> AsyncIterator[Answer | Sources]:
    # Documents rarely change between questions, so they're cached as one prefix.
    documents[-1]["cache_control"] = {"type": "ephemeral"}
    messages = [
        *recent(history),
        {"role": "user", "content": [*documents, {"type": "text", "text": question}]},
    ]
    stream = await llm.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
        stream=True,
    )
    numbers: dict[Location, int] = {}
    sources: list[Source] = []
    block_citations: list[int] = []
    async for event in stream:
        if event.type == "content_block_delta" and event.delta.type == "text_delta":
            yield Answer(event.delta.text)
        elif (
            event.type == "content_block_delta"
            and event.delta.type == "citations_delta"
        ):
            citation = event.delta.citation
            location = locate(citation)
            if location not in numbers:
                numbers[location] = len(numbers) + 1
                sources.append(
                    Source(
                        numbers[location],
                        location.document,
                        location.page_start,
                        location.page_end,
                        citation.cited_text,
                    )
                )
            if numbers[location] not in block_citations:
                block_citations.append(numbers[location])
        elif event.type == "content_block_stop" and block_citations:
            yield Answer(" " + "".join(f"[{n}]" for n in block_citations))
            block_citations = []
    yield Sources(sources)
