import pytest

from routing import RetrievalMode, route

AUTO = RetrievalMode.AUTO
FULL = RetrievalMode.FULL_CONTEXT
RAG = RetrievalMode.RAG
AGENT = RetrievalMode.AGENTIC


@pytest.mark.parametrize(
    ("mode", "tokens", "effective", "label"),
    [
        (AUTO, 50_000, FULL, "Auto → Full context"),
        (AUTO, 50_001, AGENT, "Auto → Agentic navigation"),
        (FULL, 100_000, FULL, "Full context"),
        (FULL, 100_001, AGENT, "Full context → Agentic navigation (too large)"),
        (RAG, 500, RAG, "RAG"),
        (RAG, 500_000, RAG, "RAG"),
        (AGENT, 500, AGENT, "Agentic navigation"),
    ],
)
def test_picks_the_effective_mode(mode, tokens, effective, label):
    assert route(mode, tokens) == (effective, label)
