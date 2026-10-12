from fakes import FakeChatModel, FakeEmbedder, tool_call
from langchain_core.messages import AIMessage
from pdfs import make_pdf, small_pdf

from answers import Answer, Source, Sources
from chat import Chat, ModeUsed, RetrievalMode, ToolUsed, Upload
from store import MemoryStore

PDF = "application/pdf"


async def chat_with(*replies, pdfs=None):
    pdfs = pdfs or [("invoice.pdf", small_pdf())]
    model = FakeChatModel(replies=list(replies))
    chat = Chat(store=MemoryStore(), embedder=FakeEmbedder(), chat_model=model)
    await chat.ingest("thread-1", [Upload(name, data, PDF) for name, data in pdfs])
    return chat


async def ask(chat, question="What do I owe?"):
    return [e async for e in chat.ask("thread-1", question, RetrievalMode.AGENTIC, [])]


def answer_text(events):
    return "".join(e.text for e in events if isinstance(e, Answer))


def tools_used(events):
    return [e for e in events if isinstance(e, ToolUsed)]


async def test_reads_pages_and_answers_with_numbered_citations():
    chat = await chat_with(
        tool_call("read_pages", document="invoice.pdf", first_page=1, last_page=1),
        AIMessage(content="You owe 1,250 EUR [invoice.pdf, p. 1]."),
    )

    events = await ask(chat)

    assert events[0] == ModeUsed("Agentic navigation")
    [used] = tools_used(events)
    assert used.name == "read_pages"
    assert "Total due: 1,250 EUR" in used.output
    assert answer_text(events) == "You owe 1,250 EUR [1]."
    assert events[-1] == Sources([Source(1, "invoice.pdf", 1, 1, "")])


async def test_stops_after_eight_tool_calls_and_still_answers():
    lookups = [tool_call("search", query=f"interest {n}") for n in range(10)]
    chat = await chat_with(
        *lookups, AIMessage(content="Probably 2% [invoice.pdf, p. 2].")
    )

    events = await ask(chat)

    assert len(tools_used(events)) == 8
    assert answer_text(events) == (
        "Probably 2% [1].\n\n_I stopped after 8 lookups; the answer may be incomplete._"
    )


async def test_lists_documents_and_reads_outlines_with_a_fallback():
    contract = make_pdf(
        ["Cover", "Scope", "Payment"], outline=[(1, "Scope", 2), (2, "Payment", 3)]
    )
    chat = await chat_with(
        tool_call("list_documents"),
        tool_call("get_outline", document="contract.pdf"),
        tool_call("get_outline", document="invoice.pdf"),
        AIMessage(content="Done."),
        pdfs=[("invoice.pdf", small_pdf()), ("contract.pdf", contract)],
    )

    events = await ask(chat)

    listing, contract_outline, invoice_outline = [u.output for u in tools_used(events)]
    assert listing == "invoice.pdf (2 pages)\ncontract.pdf (3 pages)"
    assert contract_outline == "p. 2: Scope\n  p. 3: Payment"
    assert invoice_outline == "p. 1: Invoice 2024-17\np. 2: Payment terms"


async def test_reads_at_most_ten_pages_at_a_time():
    report = make_pdf([f"Page {n} text" for n in range(1, 31)])
    chat = await chat_with(
        tool_call("read_pages", document="report.pdf", first_page=5, last_page=30),
        AIMessage(content="Done."),
        pdfs=[("report.pdf", report)],
    )

    [used] = tools_used(await ask(chat))

    assert "[report.pdf, p. 5]\nPage 5 text" in used.output
    assert "[report.pdf, p. 14]\nPage 14 text" in used.output
    assert "p. 15]" not in used.output


async def test_tells_the_agent_when_a_document_does_not_exist():
    chat = await chat_with(
        tool_call("read_pages", document="missing.pdf", first_page=1, last_page=1),
        AIMessage(content="Done."),
    )

    [used] = tools_used(await ask(chat))

    assert (
        used.output
        == "There is no document named 'missing.pdf'. Documents: invoice.pdf."
    )


async def test_searches_chunks_and_labels_them_with_their_pages():
    chat = await chat_with(
        tool_call("search", query="late payments interest"),
        AIMessage(content="Done."),
    )

    [used] = tools_used(await ask(chat))

    assert used.output.startswith("[invoice.pdf, pp. 1–2]\nInvoice 2024-17")


async def test_checks_quotes_before_listing_sources():
    chat = await chat_with(
        AIMessage(
            content=(
                'It says "Late payments add 2% interest per month" '
                '[invoice.pdf, p. 1] and "payment is due within fourteen days" '
                "[invoice.pdf, p. 2]."
            )
        ),
    )

    events = await ask(chat)

    assert events[-1].sources == [
        Source(1, "invoice.pdf", 2, 2, "Late payments add 2% interest per month"),
        Source(
            2,
            "invoice.pdf",
            2,
            2,
            "payment is due within fourteen days",
            "⚠️ quote not found in invoice.pdf",
        ),
    ]
