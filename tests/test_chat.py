from fakes import FakeEmbedder

from answers import Answer
from chat import Chat, RetrievalMode
from store import MemoryStore


async def ask(chat, question, mode=RetrievalMode.AUTO, history=()):
    return [
        event async for event in chat.ask("thread-1", question, mode, list(history))
    ]


def answer_text(events):
    return "".join(e.text for e in events if isinstance(e, Answer))


async def test_asks_for_a_pdf_when_the_thread_has_no_documents():
    chat = Chat(store=MemoryStore(), embedder=FakeEmbedder())

    events = await ask(chat, "What is the total on the invoice?")

    assert answer_text(events) == "Upload a PDF first, then ask me about it."


async def test_explains_what_it_can_do_without_calling_the_model():
    chat = Chat(store=MemoryStore(), embedder=FakeEmbedder())

    events = await ask(chat, "  what can you do? ")

    text = answer_text(events)
    assert "Upload PDFs" in text
    assert "Retrieval mode" in text
