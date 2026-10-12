from fakes import FakeAnthropic, FakeEmbedder, cite, text
from pdfs import make_pdf, small_pdf

from answers import Answer, Source, Sources
from chat import Chat, ModeUsed, RetrievalMode, Upload
from store import MemoryStore

PDF = "application/pdf"


async def chat_with(llm, *pdfs):
    chat = Chat(
        store=MemoryStore(), embedder=FakeEmbedder(), llm=llm, model="test-model"
    )
    await chat.ingest("thread-1", [Upload(name, data, PDF) for name, data in pdfs])
    return chat


async def ask(chat, question, history=()):
    return [
        event
        async for event in chat.ask(
            "thread-1", question, RetrievalMode.FULL_CONTEXT, list(history)
        )
    ]


def answer_text(events):
    return "".join(e.text for e in events if isinstance(e, Answer))


async def test_answers_with_numbered_citations_and_sources():
    llm = FakeAnthropic(
        [text("The invoice totals 1,250 EUR")],
        [
            text(" and is due by 30 June"),
            cite(0, 0, 1, "Total due: 1,250 EUR by 30 June."),
        ],
        [
            text(", with "),
        ],
        [
            text("2% monthly interest"),
            cite(0, 1, 2, "Late payments add 2% interest per month."),
        ],
        [text(".")],
    )
    chat = await chat_with(llm, ("invoice.pdf", small_pdf()))

    events = await ask(chat, "What do I owe?")

    assert answer_text(events) == (
        "The invoice totals 1,250 EUR and is due by 30 June [1], "
        "with 2% monthly interest [2]."
    )
    assert events[-1] == Sources(
        [
            Source(1, "invoice.pdf", 1, 1, "Total due: 1,250 EUR by 30 June."),
            Source(2, "invoice.pdf", 2, 2, "Late payments add 2% interest per month."),
        ]
    )


async def test_cites_the_right_document_and_page_range():
    contract = make_pdf(["Cover", "Scope part one", "Scope part two"])
    llm = FakeAnthropic(
        [
            text("The scope spans two pages"),
            cite(1, 1, 3, "Scope part one Scope part two"),
        ],
        [text(" and cites the invoice again"), cite(0, 0, 1, "Total due")],
        [text(" twice"), cite(0, 0, 1, "Total due")],
    )
    chat = await chat_with(
        llm, ("invoice.pdf", small_pdf()), ("contract.pdf", contract)
    )

    events = await ask(chat, "What is the scope?")

    assert answer_text(events) == (
        "The scope spans two pages [1] and cites the invoice again [2] twice [2]"
    )
    assert events[-1].sources == [
        Source(1, "contract.pdf", 2, 3, "Scope part one Scope part two"),
        Source(2, "invoice.pdf", 1, 1, "Total due"),
    ]


async def test_reports_the_mode_that_answered():
    chat = await chat_with(FakeAnthropic([text("Hi")]), ("invoice.pdf", small_pdf()))

    events = await ask(chat, "Hello?")

    assert events[0] == ModeUsed("Full context")


async def test_sends_only_the_last_ten_turns_of_history():
    llm = FakeAnthropic([text("Sure.")])
    chat = await chat_with(llm, ("invoice.pdf", small_pdf()))
    history = []
    for turn in range(15):
        history.append({"role": "user", "content": f"question {turn}"})
        history.append({"role": "assistant", "content": f"answer {turn}"})

    await ask(chat, "And now?", history)

    sent = llm.requests[0]["messages"]
    assert sent[0] == {"role": "user", "content": "question 5"}
    assert len(sent) == 21


async def test_leaves_out_empty_messages_and_starts_history_with_the_user():
    llm = FakeAnthropic([text("Sure.")])
    chat = await chat_with(llm, ("invoice.pdf", small_pdf()))
    history = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Added 1 Document."},
        {"role": "user", "content": "What is due?"},
        {"role": "assistant", "content": "1,250 EUR [1]"},
    ]

    await ask(chat, "When?", history)

    sent = llm.requests[0]["messages"]
    assert sent[:2] == history[2:]


def test_labels_a_source_with_its_pages():
    assert Source(1, "a.pdf", 4, 4, "q").label == "a.pdf, p. 4"
    assert Source(1, "a.pdf", 4, 5, "q").label == "a.pdf, pp. 4–5"
