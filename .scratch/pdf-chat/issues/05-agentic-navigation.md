# 05 — Agentic navigation

**What to build:** A third Retrieval mode, Agentic navigation. A LangGraph agent
explores the Thread's Documents: it lists them, reads Outlines, reads ranges of Pages
and searches Chunks. Each tool call shows as a Step, and the final answer streams.
After 8 tool calls, the agent answers from what it has read, with the note "I stopped
after 8 lookups; the answer may be incomplete". Its `[name, p. N]` markers are turned
into the same numbered markers and Sources list as the other modes. See the spec at
`.scratch/pdf-chat/spec.md`.

**Blocked by:** 04 — RAG mode with structure-aware Chunks

**Status:** ready-for-agent

- [ ] The settings panel offers Agentic navigation.
- [ ] The graph has an agent node and a tool node and uses `ChatAnthropic` with the same model setting as the `anthropic` client.
- [ ] The tools are `list_documents`, `get_outline` (with the fallback from first lines of Pages), `read_pages` (about 10 Pages per call) and `search` (the same Chunk search RAG uses). Each tool is limited to the current Thread.
- [ ] A counter in the graph state stops tool use at 8 calls. The agent node then runs once more without tools and adds the note. `recursion_limit` is set higher, as a safety net only.
- [ ] Tool calls appear as Chainlit Steps through `LangchainCallbackHandler`, and the final answer streams from `astream_events`.
- [ ] The prompt makes the agent cite as `[name, p. N]` or `[name, pp. N–M]` and answer only from the Documents.
- [ ] A pure Citation parser turns those markers into numbered markers and a Sources list in the same shape as the other modes.
- [ ] There is no LangGraph checkpointer. History comes from the Thread's messages.
- [ ] Unit tests use a fake chat model with scripted tool calls, and cover the tools, the cap at 8 with the note, and the shape of the Sources list. The Citation parser has its own tests.
