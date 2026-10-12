from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from answers import page_label

MAX_TOOL_CALLS = 8
PAGES_PER_READ = 10
SEARCH_RESULTS = 8
STOPPED_EARLY = (
    f"\n\n_I stopped after {MAX_TOOL_CALLS} lookups; the answer may be incomplete._"
)

SYSTEM_PROMPT = f"""\
You answer questions about the user's documents by exploring them with tools.

Start with list_documents. Use get_outline to find the relevant sections, then \
read_pages to read them (up to {PAGES_PER_READ} pages per call). Use search for \
specific facts or terms. You have {MAX_TOOL_CALLS} tool calls, so read with purpose.

Answer only from what you read; never fall back on general knowledge. If the \
documents don't contain the answer, say so plainly. Cite every claim right after \
it as [document name, p. N] or [document name, pp. N–M], using the exact document \
name. Put exact quotes from a page in double quotes. Be concise."""


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    tool_calls: int


def make_tools(store, embedder, thread_id: str) -> list:
    async def find(name: str):
        documents = await store.list_documents(thread_id)
        match = next((d for d in documents if d.name == name), None)
        names = ", ".join(d.name for d in documents)
        return match, f"There is no document named {name!r}. Documents: {names}."

    @tool
    async def list_documents() -> str:
        """List the documents in this chat with their page counts."""
        documents = await store.list_documents(thread_id)
        return "\n".join(f"{d.name} ({d.page_count} pages)" for d in documents)

    @tool
    async def get_outline(document: str) -> str:
        """Show a document's table of contents: section titles and their pages."""
        match, missing = await find(document)
        if not match:
            return missing
        outline = await store.get_outline(thread_id, match.id)
        return "\n".join(
            f"{'  ' * (entry.level - 1)}p. {entry.page}: {entry.title}"
            for entry in outline
        )

    @tool
    async def read_pages(document: str, first_page: int, last_page: int) -> str:
        """Read the text of a range of pages (at most 10 at a time)."""
        match, missing = await find(document)
        if not match:
            return missing
        first_page = max(first_page, 1)
        last_page = min(last_page, match.page_count, first_page + PAGES_PER_READ - 1)
        if first_page > last_page:
            return f"{document} has {match.page_count} pages."
        pages = await store.read_pages(thread_id, match.id, first_page, last_page)
        return "\n\n".join(
            f"[{document}, p. {number}]\n{text or '(no text layer)'}"
            for number, text in enumerate(pages, start=first_page)
        )

    @tool
    async def search(query: str) -> str:
        """Find the passages most related to a query, across all documents."""
        found = await store.search(
            thread_id, await embedder.embed_query(query), SEARCH_RESULTS
        )
        return "\n\n".join(
            f"[{page_label(f.document, f.chunk.page_start, f.chunk.page_end)}]\n"
            f"{f.chunk.text}"
            for f in found
        )

    return [list_documents, get_outline, read_pages, search]


def build_agent(chat_model, tools: list):
    explore = chat_model.bind_tools(tools)
    # Tools stay declared because the history holds tool calls; "none" forbids more.
    conclude = chat_model.bind_tools(tools, tool_choice={"type": "none"})
    run_tools = ToolNode(tools)

    async def agent(state: AgentState) -> dict:
        model = conclude if state["tool_calls"] >= MAX_TOOL_CALLS else explore
        reply = await model.ainvoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [reply]}

    async def tools_node(state: AgentState) -> dict:
        calls = len(state["messages"][-1].tool_calls)
        result = await run_tools.ainvoke(state)
        return {**result, "tool_calls": state["tool_calls"] + calls}

    def next_step(state: AgentState) -> str:
        wants_tools = bool(state["messages"][-1].tool_calls)
        return "tools" if wants_tools and state["tool_calls"] < MAX_TOOL_CALLS else END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", next_step, ["tools", END])
    graph.add_edge("tools", "agent")
    return graph.compile()
