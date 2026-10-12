from enum import StrEnum

# Up to here the whole text fits comfortably in one prompt.
AUTO_LIMIT = 5_000
# Above this, Haiku moves to its pricier long-context tier.
FULL_CONTEXT_LIMIT = 100_000


class RetrievalMode(StrEnum):
    AUTO = "Auto"
    FULL_CONTEXT = "Full context"
    RAG = "RAG"
    AGENTIC = "Agentic navigation"


def route(mode: RetrievalMode, tokens: int) -> tuple[RetrievalMode, str]:
    """Returns the mode that will answer, and a label saying how it was chosen."""
    if mode == RetrievalMode.AUTO:
        if tokens <= AUTO_LIMIT:
            effective = RetrievalMode.FULL_CONTEXT
        else:
            effective = RetrievalMode.AGENTIC
        return effective, f"{mode} → {effective}"
    if mode == RetrievalMode.FULL_CONTEXT and tokens > FULL_CONTEXT_LIMIT:
        return RetrievalMode.AGENTIC, f"{mode} → {RetrievalMode.AGENTIC} (too large)"
    return mode, str(mode)
