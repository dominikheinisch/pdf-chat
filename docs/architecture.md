# Architecture

Class and flow diagrams for the happy paths: login, uploading a PDF, and asking a
question in each Retrieval mode. Error branches (rejected or duplicate uploads, no
Documents yet) are left out. Terms follow `CONTEXT.md`.

## Modules

```
              ┌─────────────────────────── src/app.py ───────────────────────────┐
  Browser ──▶ │ Chainlit hooks: login, on_chat_start, on_chat_resume,            │
              │ on_settings_update, on_message, quick_reply → ingest() / answer()│
              └──────┬──────────────────────────────────────────────┬────────────┘
                     │ Chat.ingest / Chat.ask                        │ data layer
                     ▼                                               ▼
              ┌──────────────┐                              ┌─────────────────┐
              │   chat.py    │                              │ attachments.py  │
              │    Chat      │                              │ AttachmentStore │──▶ /data/attachments
              └──┬───┬───┬───┘                              └─────────────────┘
     ingest      │   │   │      ask
   ┌─────────────┘   │   └──────────────────────────────┐
   ▼                 ▼                                  ▼
 extraction.py   routing.py ── route() ──▶ ┌────────────┬───────────┬───────────────┐
 chunking.py                               │ Full ctx   │ RAG       │ Agentic       │
 embeddings.py                             │ answers.py │ answers.py│ agent.py      │
   │                                       │            │           │ citations.py  │
   │                                       │            │           │ quotes.py     │
   ▼                                       └─────┬──────┴─────┬─────┴──────┬────────┘
 store.py  ◀─────────────────────────────────────┴────────────┴────────────┘
 PostgresStore ──▶ Postgres + pgvector (documents, chunks; Chainlit's Thread, Step…)
```

## Classes

```
┌──────────────────────────────┐        ┌───────────────────────────────┐
│ Settings  (config.py)        │        │ AttachmentStore (attachments) │
├──────────────────────────────┤        │   extends BaseStorageClient   │
│ anthropic_api_key: SecretStr │        ├───────────────────────────────┤
│ llm_model = claude-haiku-5-5 │        │ root: Path                    │
│ demo_username / demo_password│        │ router: APIRouter             │
│ database_url                 │        ├───────────────────────────────┤
│ attachments_dir: Path        │        │ mount(app)                    │
└──────────────────────────────┘        │ upload_file(key, data, mime…) │
                                        │ delete_file(key)              │
                                        │ get_read_url(key)             │
                                        │ _serve(key, user) → PDF inline│
                                        └───────────────────────────────┘

┌──────────────────────────────────────────┐
│ Chat  (chat.py)                          │
├──────────────────────────────────────────┤        ┌────────────────────────┐
│ store: PostgresStore | MemoryStore  ─────┼───────▶│ PostgresStore          │
│ embedder: FastEmbedder              ─────┼──┐     ├────────────────────────┤
│ llm: AsyncAnthropic                      │  │     │ pool: asyncpg.Pool     │
│ model: str                               │  │     ├────────────────────────┤
│ chat_model: ChatAnthropic (LangChain)    │  │     │ add_document(…) → id   │
├──────────────────────────────────────────┤  │     │ has_document(hash)     │
│ ingest(thread, [Upload]) → IngestReport  │  │     │ list_documents()       │
│ ask(thread, q, mode, history)            │  │     │   → [DocumentInfo]     │
│   → async iter of ModeUsed | ToolUsed    │  │     │ load_documents()       │
│                 | Answer | Sources       │  │     │   → [StoredDocument]   │
│ _full_context / _rag / _agentic          │  │     │ search(vec, k)         │
└──────────────────────────────────────────┘  │     │   → [FoundChunk]       │
                                              │     │ get_outline(doc_id)    │
                       ┌──────────────────────┘     │ read_pages(id, a, b)   │
                       ▼                            └────────────────────────┘
          ┌───────────────────────────┐              MemoryStore: same interface,
          │ FastEmbedder              │              in memory, used by the tests
          ├───────────────────────────┤
          │ model: bge-small-en-v1.5  │
          │ embed_passages([str])     │
          │ embed_query(str) → [384f] │
          └───────────────────────────┘

 Ingestion values                         Retrieval values
 ────────────────                         ────────────────
 Upload(name, data, mime)                 RetrievalMode: AUTO | FULL_CONTEXT | RAG | AGENTIC
 Document(name, content_hash,             route(mode, tokens) → (effective mode, label)
          pages[], outline[])             DocumentInfo(id, name, page_count, tokens)
   .tokens  .pages_without_text           StoredDocument(id, name, pages[])
 OutlineEntry(level, title, page)         FoundChunk(document, Chunk)
 Chunk(text, page_start, page_end)        Location(document, page_start, page_end)
 FileResult(name, Outcome, message)
 IngestReport(files[])                    Events streamed by Chat.ask
   .summary  .quick_replies               ───────────────────────────
 Outcome: ADDED | SKIPPED | REJECTED      ModeUsed(label)
                                          ToolUsed(name, input, output)
 Citation helpers                         Answer(text)
 ────────────────                         Sources([Source])
 CitationNumbering   "[doc, p. N]" → "[1]"  Source(number, document, page_start,
   .feed(text) .flush() .sources                   page_end, quote, warning)
 check_quotes(answer, sources, pages)        .label → "doc, p. N" / "doc, pp. N–M"

 Agent (agent.py)
 ────────────────
 AgentState { messages: [AnyMessage] (add_messages), tool_calls: int }
 make_tools(store, embedder, thread) → [list_documents, get_outline, read_pages, search]
 build_agent(chat_model, tools) → compiled StateGraph
```

### Database

```
  "Thread" (Chainlit)          documents                         chunks
 ┌──────────────┐ 1      * ┌────────────────────────┐ 1     * ┌───────────────────┐
 │ id           │◀─────────│ thread_id  (CASCADE)   │◀────────│ document_id       │
 │ …            │          │ id, name, content_hash │         │ position, text    │
 └──────────────┘          │ pages TEXT[]           │         │ page_start/end    │
                           │ outline JSONB, tokens  │         │ embedding vec(384)│
                           │ UNIQUE(thread, hash)   │         └───────────────────┘
                           └────────────────────────┘
```

## Startup and login

```
 Container start
   │
   ├─ Settings()                         read env, fail fast on missing keys
   ├─ AttachmentStore(dir).mount(server) /attachments/{key} ahead of Chainlit's UI route
   ├─ @data_layer → ChainlitDataLayer(db_url, storage_client=attachments)
   └─ @on_app_startup
        connect(db_url) → asyncpg pool (pgvector registered)
        chat = Chat(PostgresStore, FastEmbedder, AsyncAnthropic, model, ChatAnthropic)

 User              app.py                         Chainlit
  │ username/pw ──▶ login(): compare_digest both ──▶ cl.User
  │ open new chat ─▶ on_chat_start: history = [], send_settings(Auto)
  │ ◀──────────────  starters + "Retrieval mode" select
```

## Upload a PDF

```
 User         app.py                   Chat                 extraction / chunking / embeddings      PostgresStore
  │ msg+PDF ──▶ on_message
  │             files = elements with path
  │             ingest(files)
  │             for each file:
  │               cl.Step "Processing x.pdf"
  │               Upload(name, bytes, mime)
  │               ───────────────────────▶ ingest(thread, [upload])
  │                                        _ingest:
  │                                          mime == application/pdf ✓
  │                                          ───────────────────▶ extract(bytes, name)  [thread]
  │                                                                 %PDF- header, pymupdf.open
  │                                                                 page_text() per page (blocks)
  │                                                                 get_toc() or first_lines()
  │                                          ◀─────────────────── Document(name, sha256, pages, outline)
  │                                          ─────────────────────────────────────────────────────▶ has_document(hash)
  │                                          ◀───────────────────────────────────────────────────── False
  │                                          ───────────────────▶ chunk(pages)  [thread]
  │                                                                 sentences → ~800 tok chunks,
  │                                                                 100 tok overlap, break at headings
  │                                          ◀─────────────────── [Chunk(text, page_start, page_end)]
  │                                          ───────────────────▶ embed_passages(texts)
  │                                          ◀─────────────────── [[384 floats]]
  │                                          ─────────────────────────────────────────────────────▶ add_document(…)
  │                                                                                                   one tx:
  │                                                                                                   INSERT "Thread" ON CONFLICT
  │                                                                                                   INSERT documents
  │                                                                                                   INSERT chunks (executemany)
  │                                          ◀───────────────────────────────────────────────────── document_id
  │               ◀──────────────────────  IngestReport([FileResult(ADDED, warning?)])
  │               step.output = "added"
  │             IngestReport(all results)
  │ ◀────────── "Added 1 Document." + quick replies [Summarize x.pdf] [Key points of x.pdf]

 In parallel, Chainlit's data layer saves the Attachment itself:
   ChainlitDataLayer ──▶ AttachmentStore.upload_file(key, bytes) ──▶ <dir>/<key> + <key>.json
   On resume the browser fetches GET /attachments/<key> (logged-in user only) → PDF inline.
```

## Ask a question

Shared front half, then one of three answer flows.

```
 User          app.py                                Chat.ask
  │ question ─▶ on_message  (or quick_reply click: post it as user msg)
  │             answer(question)
  │               mode = user_session["mode"]
  │               ────────────────────────────────▶ ask(thread, q, mode, history)
  │                                                   store.list_documents(thread)
  │                                                   tokens = Σ d.tokens   (chars / 4)
  │                                                   route(mode, tokens)
  │                                                   ┌──────────────────────────────────────────┐
  │                                                   │ Auto,  tokens ≤ 5k      → Full context   │
  │                                                   │ Auto,  tokens > 5k      → Agentic        │
  │                                                   │ Full,  tokens > 100k    → Agentic        │
  │                                                   │ otherwise               → mode as chosen │
  │                                                   └──────────────────────────────────────────┘
  │               ◀──────────────────────────────── ModeUsed("Auto → Full context")
  │                                                   dispatch to _full_context | _rag | _agentic
  │               ◀──────────────────────────────── Answer(text)*   → reply.stream_token
  │               ◀──────────────────────────────── ToolUsed*       → cl.Step (agent only)
  │               ◀──────────────────────────────── Sources([...])  → "Sources" list + side cl.Text
  │               history += user, assistant
  │               stream "*Mode: …*", reply.send()
  │ ◀──────────── answer with [1] [2] markers, Sources panel
```

### Full context

```
 Chat._full_context                     answers.stream_answer                 Claude Messages API
  │ store.load_documents(thread)
  │ blocks = document_block(name, pages)    one content block per Page,
  │          per Document                   citations enabled
  │ ─────────────────────────────────────▶ last block: cache_control ephemeral
  │                                         messages = recent(history, 10 turns)
  │                                                    + [blocks…, question]
  │                                         ────────────────────────────────▶ messages.create(stream=True)
  │                                         ◀──────────────────────────────── text_delta
  │ ◀──────────────────────────────────── Answer(text)
  │                                         ◀──────────────────────────────── citations_delta
  │                                           locate(citation):
  │                                             documents[document_index],
  │                                             pages start_block+1 .. end_block
  │                                           new Location → Source(n, …, cited_text)
  │                                         ◀──────────────────────────────── content_block_stop
  │ ◀──────────────────────────────────── Answer(" [1][2]")
  │                                         … stream ends
  │ ◀──────────────────────────────────── Sources([Source…])
```

### RAG

```
 Chat._rag                                                         answers.stream_answer
  │ embedder.embed_query(question) → vec
  │ store.search(thread, vec, 8)
  │   ORDER BY embedding <=> vec LIMIT 8   → [FoundChunk(doc, Chunk)]
  │ blocks = document_block("doc, pp. a–b", [chunk.text])  per chunk
  │ ───────────────────────────────────────────────────────────▶ same as Full context, but
  │                                                               locate(citation) = found[document_index]
  │                                                                 → Location(doc, chunk.page_start,
  │                                                                            chunk.page_end)
  │ ◀─────────────────────────────────────────────────────────── Answer* … Sources
```

### Agentic navigation

```
 Chat._agentic
  │ tools = make_tools(store, embedder, thread)
  │ graph = build_agent(chat_model, tools)
  │ state = { messages: recent(history) + [Human(question)], tool_calls: 0 }
  │ numbering = CitationNumbering()
  │ graph.astream_events(state, recursion_limit = 32)
  │
  │      ┌──────────── LangGraph ─────────────────────────────────────────────┐
  │      │                                                                    │
  │      │  START ──▶ agent ───── next_step ──── wants tools and ──▶ tools    │
  │      │              ▲         (conditional)   tool_calls < 8      │       │
  │      │              │              │                              │       │
  │      │              │              └── no tool calls, or ≥ 8 ──▶ END      │
  │      │              └─────────────────────────────────────────────┘       │
  │      │                                                                    │
  │      │  agent: tool_calls < 8 ? explore (tools bound)                     │
  │      │                        : conclude (tool_choice none)               │
  │      │         ainvoke([System(prompt), *messages]) → AIMessage           │
  │      │  tools: ToolNode runs the calls, tool_calls += len(calls)          │
  │      │         list_documents()            → "x.pdf (42 pages)"           │
  │      │         get_outline(doc)            → "p. 3: Introduction" …       │
  │      │         read_pages(doc, a, b)       → "[x.pdf, p. 3]\n…" (≤10 pp.) │
  │      │         search(query)               → top 8 chunks with labels     │
  │      └────────────────────────────────────────────────────────────────────┘
  │
  │ per event:
  │   on_chat_model_stream ─▶ numbering.feed(text)
  │                             holds back an open "[" until it closes,
  │                             "[x.pdf, p. 3]" → "[1]", records Source(1, x.pdf, 3, 3)
  │                           ─▶ yield Answer(text)
  │   on_tool_end          ─▶ yield ToolUsed(name, input, output)   → cl.Step in the UI
  │
  │ numbering.flush()      ─▶ yield Answer(rest)
  │ (tool_calls ≥ 8        ─▶ yield Answer("I stopped after 8 lookups…"))
  │ store.load_documents(thread) → {name: pages}
  │ check_quotes(answer, numbering.sources, pages)
  │   for each "quote" of ≥ 5 words followed by [n] within 120 chars:
  │     normalise (NFKC, line-end hyphens, case, spaces)
  │     on the cited pages        → keep, attach quote
  │     on another page of doc    → move citation there
  │     nowhere                   → warning "⚠️ quote not found in doc"
  └─▶ yield Sources([...])
```

## Resume a Thread

```
 User           app.py                              Chainlit data layer / AttachmentStore
  │ open old ──▶ on_chat_resume(thread)
  │ thread       history = user/assistant steps from thread["steps"]
  │              send_settings(saved mode or Auto)
  │ ◀─────────── messages with Attachments and Sources panels ◀── Postgres steps + elements
  │ GET /attachments/<key> ─────────────────────────────────────▶ _serve: user? → FileResponse
  │                                                                (PDF inline, else download)
  │ next question → "Ask a question" above; Documents are already in Postgres for this Thread
```
