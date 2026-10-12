from pathlib import Path
from secrets import compare_digest

import chainlit as cl
from anthropic import AsyncAnthropic
from chainlit.element import Element
from chainlit.input_widget import Select
from chainlit.types import ThreadDict
from langchain_anthropic import ChatAnthropic

from answers import Answer, Sources
from chat import (
    Chat,
    IngestReport,
    ModeUsed,
    Outcome,
    RetrievalMode,
    ToolUsed,
    Upload,
)
from config import Settings
from embeddings import FastEmbedder
from store import PostgresStore, connect

# Fails at startup when a required setting such as ANTHROPIC_API_KEY is missing.
settings = Settings()
chat: Chat

MODES = [RetrievalMode.FULL_CONTEXT, RetrievalMode.RAG, RetrievalMode.AGENTIC]
DEFAULT_MODE = RetrievalMode.FULL_CONTEXT


@cl.on_app_startup
async def startup() -> None:
    global chat
    store = PostgresStore(await connect(settings.database_url))
    api_key = settings.anthropic_api_key.get_secret_value()
    chat = Chat(
        store,
        FastEmbedder(),
        llm=AsyncAnthropic(api_key=api_key),
        model=settings.llm_model,
        chat_model=ChatAnthropic(
            model=settings.llm_model, api_key=api_key, max_tokens=4096
        ),
    )


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
    await send_settings(DEFAULT_MODE)


@cl.on_chat_resume
async def resume(thread: ThreadDict) -> None:
    roles = {"user_message": "user", "assistant_message": "assistant"}
    history = [
        {"role": roles[step["type"]], "content": step["output"] or ""}
        for step in thread["steps"]
        if step["type"] in roles
    ]
    cl.user_session.set("history", history)
    # The mode comes back with the session, but the settings panel must be re-sent.
    await send_settings(cl.user_session.get("mode", DEFAULT_MODE))


@cl.on_settings_update
async def on_settings_update(values: dict) -> None:
    cl.user_session.set("mode", values["mode"])


async def send_settings(mode: str) -> None:
    values = await cl.ChatSettings(
        [
            Select(
                id="mode",
                label="Retrieval mode",
                values=list(MODES),
                initial_index=MODES.index(mode),
            )
        ]
    ).send()
    cl.user_session.set("mode", values["mode"])


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
    effective_mode = None
    text = ""
    mode = RetrievalMode(cl.user_session.get("mode", DEFAULT_MODE))
    async for event in chat.ask(thread_id, question, mode, history):
        if isinstance(event, ModeUsed):
            effective_mode = event.label
        elif isinstance(event, ToolUsed):
            async with cl.Step(name=event.name, type="tool") as step:
                step.input = event.input
                step.output = event.output
        elif isinstance(event, Answer):
            text += event.text
            await reply.stream_token(event.text)
        elif isinstance(event, Sources) and event.sources:
            await add_sources(reply, event)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": text})
    if effective_mode:
        await reply.stream_token(f"\n\n*Mode: {effective_mode}*")
    await reply.send()


async def add_sources(reply: cl.Message, sources: Sources) -> None:
    lines = ["\n\n**Sources**"]
    for source in sources.sources:
        name = f"Source {source.number}"
        warning = f" {source.warning}" if source.warning else ""
        lines.append(f"{source.number}. {source.label} ({name}){warning}")
        content = f"**{source.label}**"
        if source.warning:
            content += f"\n\n{source.warning}"
        if source.quote:
            content += f"\n\n> {source.quote}"
        reply.elements.append(cl.Text(name=name, content=content, display="side"))
    await reply.stream_token("\n".join(lines))
