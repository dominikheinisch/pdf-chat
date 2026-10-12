from secrets import compare_digest

import chainlit as cl

from chat import Answer, Chat, RetrievalMode
from config import Settings
from store import MemoryStore

# Fails at startup when a required setting such as ANTHROPIC_API_KEY is missing.
settings = Settings()
chat = Chat(store=MemoryStore())


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


@cl.on_message
async def on_message(message: cl.Message) -> None:
    thread_id = cl.context.session.thread_id
    reply = cl.Message(content="")
    async for event in chat.ask(thread_id, message.content, RetrievalMode.AUTO, []):
        if isinstance(event, Answer):
            await reply.stream_token(event.text)
    await reply.send()
