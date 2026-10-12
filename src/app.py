from pathlib import Path
from secrets import compare_digest

import asyncpg
import chainlit as cl
from chainlit.element import Element
from chainlit.types import ThreadDict

from chat import Answer, Chat, IngestReport, Outcome, RetrievalMode, Upload
from config import Settings
from store import PostgresStore

# Fails at startup when a required setting such as ANTHROPIC_API_KEY is missing.
settings = Settings()
chat: Chat


@cl.on_app_startup
async def startup() -> None:
    global chat
    pool = await asyncpg.create_pool(settings.database_url)
    chat = Chat(store=PostgresStore(pool))


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


@cl.on_chat_resume
async def resume(thread: ThreadDict) -> None:
    pass


@cl.on_message
async def on_message(message: cl.Message) -> None:
    files = [e for e in message.elements if getattr(e, "path", None)]
    if files:
        await ingest(files)
    if message.content.strip():
        await answer(message.content)


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
    await cl.Message(content=describe(report)).send()


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
    reply = cl.Message(content="")
    async for event in chat.ask(thread_id, question, RetrievalMode.AUTO, []):
        if isinstance(event, Answer):
            await reply.stream_token(event.text)
    await reply.send()
