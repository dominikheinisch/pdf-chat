from pathlib import Path
from secrets import compare_digest

import asyncpg
import chainlit as cl
from anthropic import AsyncAnthropic
from chainlit.element import Element
from chainlit.types import ThreadDict

from answers import Answer, Sources
from chat import Chat, IngestReport, ModeUsed, Outcome, RetrievalMode, Upload
from config import Settings
from store import PostgresStore

# Fails at startup when a required setting such as ANTHROPIC_API_KEY is missing.
settings = Settings()
chat: Chat


@cl.on_app_startup
async def startup() -> None:
    global chat
    pool = await asyncpg.create_pool(settings.database_url)
    llm = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    chat = Chat(store=PostgresStore(pool), llm=llm, model=settings.llm_model)


@cl.password_auth_callback
async def login(username: str, password: str) -> cl.User | None:
    # Check both fields so the response time doesn't reveal which one was wrong.
    user_ok = compare_digest(username.encode(), settings.demo_username.encode())
    password_ok = compare_digest(
        password.encode(), settings.demo_password.get_secret_value().encode()
    )
    return cl.User(identifier=username) if user_ok and password_ok else None


@cl.set_starters
async def starters() -> list[cl.Starter]:
    return [
        cl.Starter(label="Upload a PDF to begin", message="How do I start?"),
        cl.Starter(label="What can you do?", message="What can you do?"),
    ]


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("history", [])


@cl.on_chat_resume
async def resume(thread: ThreadDict) -> None:
    roles = {"user_message": "user", "assistant_message": "assistant"}
    history = [
        {"role": roles[step["type"]], "content": step["output"] or ""}
        for step in thread["steps"]
        if step["type"] in roles
    ]
    cl.user_session.set("history", history)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    files = [e for e in message.elements if getattr(e, "path", None)]
    if files:
        await ingest(files)
    if message.content.strip():
        await answer(message.content)


@cl.action_callback("quick_reply")
async def on_quick_reply(action: cl.Action) -> None:
    # Only typed messages reach on_message, so post the click as the user's turn.
    question = action.payload["text"]
    await action.remove()
    await cl.Message(content=question, type="user_message").send()
    await answer(question)


async def ingest(files: list[Element]) -> None:
    thread_id = cl.context.session.thread_id
    results = []
    for file in files:
        async with cl.Step(name=f"Processing {file.name}", type="tool") as step:
            upload = Upload(file.name, Path(file.path).read_bytes(), file.mime or "")
            report = await chat.ingest(thread_id, [upload])
            step.output = report.files[0].message or report.files[0].outcome
        results.extend(report.files)
    report = IngestReport(results)
    actions = [
        cl.Action(name="quick_reply", payload={"text": text}, label=text)
        for text in report.quick_replies
    ]
    await cl.Message(content=describe(report), actions=actions).send()


def describe(report: IngestReport) -> str:
    lines = [report.summary]
    for file in report.files:
        if file.outcome == Outcome.REJECTED:
            lines.append(f"- **{file.name}** was rejected: {file.message}")
        elif file.outcome == Outcome.SKIPPED:
            lines.append(f"- **{file.name}** was skipped: {file.message}")
        elif file.message:
            lines.append(f"- **{file.name}**: {file.message}")
    return "\n".join(lines)


async def answer(question: str) -> None:
    thread_id = cl.context.session.thread_id
    history = cl.user_session.get("history", [])
    reply = cl.Message(content="")
    mode = None
    text = ""
    async for event in chat.ask(thread_id, question, RetrievalMode.AUTO, history):
        if isinstance(event, ModeUsed):
            mode = event.label
        elif isinstance(event, Answer):
            text += event.text
            await reply.stream_token(event.text)
        elif isinstance(event, Sources) and event.sources:
            await add_sources(reply, event)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": text})
    if mode:
        await reply.stream_token(f"\n\n*Mode: {mode}*")
    await reply.send()


async def add_sources(reply: cl.Message, sources: Sources) -> None:
    lines = ["\n\n**Sources**"]
    for source in sources.sources:
        name = f"Source {source.number}"
        lines.append(f"{source.number}. {source.label} ({name})")
        reply.elements.append(
            cl.Text(
                name=name,
                content=f"**{source.label}**\n\n> {source.quote}",
                display="side",
            )
        )
    await reply.stream_token("\n".join(lines))
