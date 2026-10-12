import re

from answers import Source

CITATION = re.compile(r"\[([^\[\]]+?), pp?\. (\d+)(?:\s*[–-]\s*(\d+))?\]")
# An unclosed "[" longer than this can't be a citation, so it's let through.
MAX_CITATION = 200


class CitationNumbering:
    """Turns "[name, p. N]" markers into "[1]", "[2]", ... as text streams in."""

    def __init__(self):
        self.sources: list[Source] = []
        self._pending = ""

    def feed(self, text: str) -> str:
        self._pending += text
        start = self._pending.rfind("[")
        if (
            start == -1
            or "]" in self._pending[start:]
            or len(self._pending) - start > MAX_CITATION
        ):
            ready, self._pending = self._pending, ""
        else:
            ready, self._pending = self._pending[:start], self._pending[start:]
        return CITATION.sub(self._number, ready)

    def flush(self) -> str:
        ready, self._pending = self._pending, ""
        return CITATION.sub(self._number, ready)

    def _number(self, match: re.Match) -> str:
        document, first, last = match.group(1), int(match.group(2)), match.group(3)
        last = int(last) if last else first
        for source in self.sources:
            if (source.document, source.page_start, source.page_end) == (
                document,
                first,
                last,
            ):
                return f"[{source.number}]"
        source = Source(len(self.sources) + 1, document, first, last, "")
        self.sources.append(source)
        return f"[{source.number}]"
