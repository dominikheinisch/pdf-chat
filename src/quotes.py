import re
import unicodedata
from dataclasses import replace

from answers import Source

MIN_WORDS = 5
QUOTE = re.compile(r"[\"“]([^\"“”]+)[\"”]")
MARKER = re.compile(r"\[(\d+)\]")
# How far after a quote its citation marker may appear.
MARKER_REACH = 120


def check_quotes(
    answer: str, sources: list[Source], pages: dict[str, list[str]]
) -> list[Source]:
    """Checks quoted text against the stored pages of the source it cites.

    A quote found on another page of the same document moves the citation there;
    a quote found nowhere in the document is flagged.
    """
    by_number = {s.number: s for s in sources}
    for quote, number in cited_quotes(answer):
        source = by_number.get(number)
        if source is None or source.document not in pages:
            continue
        document_pages = [normalise(p) for p in pages[source.document]]
        wanted = normalise(quote)
        cited = range(source.page_start, source.page_end + 1)
        if any(
            wanted in document_pages[n - 1] for n in cited if n <= len(document_pages)
        ):
            by_number[number] = replace(source, quote=source.quote or quote)
            continue
        page = next(
            (n for n, text in enumerate(document_pages, start=1) if wanted in text),
            None,
        )
        if page:
            by_number[number] = replace(
                source, page_start=page, page_end=page, quote=quote
            )
        else:
            by_number[number] = replace(
                source,
                quote=quote,
                warning=f"⚠️ quote not found in {source.document}",
            )
    return [by_number[s.number] for s in sources]


def cited_quotes(answer: str) -> list[tuple[str, int]]:
    result = []
    for match in QUOTE.finditer(answer):
        quote = match.group(1).strip()
        if len(quote.split()) < MIN_WORDS:
            continue
        after = answer[match.end() : match.end() + MARKER_REACH]
        after = QUOTE.split(after)[0]
        if marker := MARKER.search(after):
            result.append((quote, int(marker.group(1))))
    return result


def normalise(text: str) -> str:
    # NFKC unfolds ligatures such as "ﬁ"; a hyphen at a line end splits a word.
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"-\s*\n\s*", "", text)
    return " ".join(text.lower().split())
