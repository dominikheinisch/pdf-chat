import re
from dataclasses import dataclass

CHUNK_TOKENS = 800
OVERLAP_TOKENS = 100
# A short one-line paragraph without closing punctuation reads as a heading.
HEADING_CHARS = 80
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    text: str
    page_start: int
    page_end: int


@dataclass(frozen=True)
class Sentence:
    text: str
    page: int
    starts_paragraph: bool
    is_heading: bool = False


def chunk(pages: list[str]) -> list[Chunk]:
    """Packs whole sentences into chunks, across page breaks.

    A chunk closes when the next sentence would overflow it, or at a heading once
    it's half full, so sections tend to start their own chunk. Chunks that close
    mid-section repeat their last ~100 tokens at the start of the next one.
    """
    chunks = []
    current: list[Sentence] = []
    for sentence in sentences(pages):
        if current and sentence.is_heading and tokens(current) >= CHUNK_TOKENS // 2:
            chunks.append(to_chunk(current))
            current = []
        elif current and tokens([*current, sentence]) > CHUNK_TOKENS:
            chunks.append(to_chunk(current))
            current = overlap(current)
        current.append(sentence)
    if current:
        chunks.append(to_chunk(current))
    return chunks


def sentences(pages: list[str]) -> list[Sentence]:
    result = []
    for number, text in enumerate(pages, start=1):
        for paragraph in text.split("\n\n"):
            paragraph = " ".join(paragraph.split())
            parts = [p for p in SENTENCE_END.split(paragraph) if p]
            heading = (
                len(parts) == 1
                and len(paragraph) <= HEADING_CHARS
                and not paragraph.endswith((".", "!", "?", ":", ";", ","))
            )
            for index, part in enumerate(parts):
                for position, piece in enumerate(split_long(part)):
                    starts = index == 0 and position == 0
                    result.append(Sentence(piece, number, starts, heading))
    return result


def split_long(sentence: str) -> list[str]:
    limit = (CHUNK_TOKENS - OVERLAP_TOKENS) * 4
    if len(sentence) <= limit:
        return [sentence]
    pieces, words = [], sentence.split(" ")
    piece = ""
    for word in words:
        if piece and len(piece) + len(word) + 1 > limit:
            pieces.append(piece)
            piece = word
        else:
            piece = f"{piece} {word}" if piece else word
    return [*pieces, piece]


def overlap(sentences: list[Sentence]) -> list[Sentence]:
    kept: list[Sentence] = []
    for sentence in reversed(sentences):
        if tokens([sentence, *kept]) > OVERLAP_TOKENS:
            break
        kept.insert(0, sentence)
    return kept


def tokens(sentences: list[Sentence]) -> int:
    return sum(len(s.text) + 2 for s in sentences) // 4


def to_chunk(sentences: list[Sentence]) -> Chunk:
    text = sentences[0].text
    for sentence in sentences[1:]:
        text += ("\n\n" if sentence.starts_paragraph else " ") + sentence.text
    return Chunk(text, sentences[0].page, sentences[-1].page)
