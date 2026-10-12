from fakes import FakeAnthropic, FakeChatModel, FakeEmbedder, text
from langchain_core.messages import AIMessage
from pdfs import large_pdf, small_pdf

from chat import Chat, ModeUsed, RetrievalMode, Upload
from store import MemoryStore

PDF = "application/pdf"


async def ask_in_auto(pdf):
    llm = FakeAnthropic([text("From the full text.")])
    agent = FakeChatModel(replies=[AIMessage(content="From the agent.")])
    chat = Chat(MemoryStore(), FakeEmbedder(), llm=llm, model="m", chat_model=agent)
    await chat.ingest("thread-1", [Upload("doc.pdf", pdf, PDF)])
    return [e async for e in chat.ask("thread-1", "Summary?", RetrievalMode.AUTO, [])]


async def test_auto_reads_a_small_document_in_full():
    events = await ask_in_auto(small_pdf())

    assert events[0] == ModeUsed("Auto → Full context")


async def test_auto_sends_a_large_document_to_the_agent():
    events = await ask_in_auto(large_pdf(150))

    assert events[0] == ModeUsed("Auto → Agentic navigation")
