from types import SimpleNamespace as Event


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
