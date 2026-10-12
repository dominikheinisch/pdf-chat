import json
import re
from types import SimpleNamespace as Event

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field


def text(value):
    return ("text", value)


def cite(document_index, first_block, end_block, quote):
    return ("cite", document_index, first_block, end_block, quote)


class FakeAnthropic:
    """Streams a scripted answer. Each block is a list of text and cite parts."""

    def __init__(self, *blocks):
        self.blocks = blocks
        self.requests = []
        self.messages = self

    async def create(self, **request):
        self.requests.append(request)
        return self._stream()

    async def _stream(self):
        for index, block in enumerate(self.blocks):
            yield Event(
                type="content_block_start",
                index=index,
                content_block=Event(type="text", text=""),
            )
            for part in block:
                if part[0] == "text":
                    delta = Event(type="text_delta", text=part[1])
                else:
                    _, document_index, first, end, quote = part
                    delta = Event(
                        type="citations_delta",
                        citation=Event(
                            type="content_block_location",
                            document_index=document_index,
                            start_block_index=first,
                            end_block_index=end,
                            cited_text=quote,
                        ),
                    )
                yield Event(type="content_block_delta", index=index, delta=delta)
            yield Event(type="content_block_stop", index=index)
        yield Event(type="message_stop")


class FakeEmbedder:
    """Bag-of-words vectors: texts sharing words end up close together."""

    dimensions = 384

    async def embed_passages(self, texts):
        return [self._embed(text) for text in texts]

    async def embed_query(self, text):
        return self._embed(text)

    def _embed(self, text):
        vector = [0.0] * self.dimensions
        for word in text.lower().split():
            word = word.strip(".,:;!?")
            vector[sum(map(ord, word)) % self.dimensions] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]


class FakeChatModel(BaseChatModel):
    """Replies with scripted messages, streamed word by word like a real model."""

    replies: list[AIMessage]
    calls: list[dict] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[t.name for t in tools], **kwargs)

    def _next(self, messages, kwargs) -> AIMessage:
        self.calls.append({"messages": messages, **kwargs})
        if kwargs.get("tool_choice") == {"type": "none"}:
            # Like the API: a model told not to use tools answers in text.
            self.replies = [r for r in self.replies if not r.tool_calls]
        return self.replies.pop(0)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=self._next(messages, kwargs))]
        )

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        reply = self._next(messages, kwargs)
        for word in re.split(r"(\s+)", reply.content):
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=word))
            if run_manager:
                await run_manager.on_llm_new_token(word, chunk=chunk)
            yield chunk
        if reply.tool_calls:
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": c["name"],
                            "args": json.dumps(c["args"]),
                            "id": c["id"],
                            "index": i,
                        }
                        for i, c in enumerate(reply.tool_calls)
                    ],
                )
            )


def tool_call(name, **args):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call-{name}-{id(args)}"}],
    )
