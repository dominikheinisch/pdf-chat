from fakes import FakeAnthropic, FakeEmbedder, cite, text
from pdfs import large_pdf, make_pdf, small_pdf

from answers import Source
from chat import Chat, ModeUsed, RetrievalMode, Upload
from store import MemoryStore

PDF = "application/pdf"


async def chat_with(llm, *pdfs):
    chat = Chat(store=MemoryStore(), llm=llm, model="m", embedder=FakeEmbedder())
    await chat.ingest("thread-1", [Upload(name, data, PDF) for name, data in pdfs])
    return chat


async def ask(chat, question):
    return [e async for e in chat.ask("thread-1", question, RetrievalMode.RAG, [])]


async def test_answers_from_the_most_relevant_chunk_and_cites_its_pages():
    contract = make_pdf(
        ["Cover page", "The warranty covers repairs for two years after delivery."]
    )
    llm = FakeAnthropic([text("Two years"), cite(0, 0, 1, "two years")])
    chat = await chat_with(
        llm, ("invoice.pdf", small_pdf()), ("contract.pdf", contract)
    )

    events = await ask(chat, "How long does the warranty cover repairs?")

    assert events[0] == ModeUsed("RAG")
    assert events[-1].sources == [Source(1, "contract.pdf", 1, 2, "two years")]
    first_block = llm.requests[0]["messages"][-1]["content"][0]
    assert first_block["title"] == "contract.pdf, pp. 1–2"


async def test_sends_only_the_top_eight_chunks():
    llm = FakeAnthropic([text("Something.")])
    chat = await chat_with(llm, ("report.pdf", large_pdf(60)))

    await ask(chat, "What does topic 7 explain?")

    content = llm.requests[0]["messages"][-1]["content"]
    assert len([block for block in content if block["type"] == "document"]) == 8
