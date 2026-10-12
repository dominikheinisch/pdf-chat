# PDF chat: design decisions

Decisions for turning the Chainlit POC (`chainlit-example` branch) into an agentic
chat app where users upload PDFs of varying size and quality and chat with them.
Domain terms (Thread, Document, Page, Chunk, Retrieval mode, Effective mode, Citation,
Quote check, and so on) are defined in [`CONTEXT.md`](../CONTEXT.md).

## UI and access

- **Chainlit is the chat UI.** It also provides the auth hooks, the settings panel,
  streaming and Thread history.
- **One demo account from environment variables.** The login exists only because
  Chainlit needs a user to save Threads. The account comes from `DEMO_USERNAME` and
  `DEMO_PASSWORD`.
- **PDFs can be uploaded at any point** with the paperclip button
  (`spontaneous_file_upload`). Each one becomes a Document of the Thread, and Auto
  recalculates.
- **Several PDFs in one message** each get their own "Processing…" step, followed by a
  summary such as "Added 3 Documents (1 skipped as duplicate)".
- **Starters are about PDFs:** "Upload a PDF to begin" and "What can you do?".
- **Quick replies name the new Documents.** After one Document is added, they are
  "Summarize invoice.pdf" and "Key points of invoice.pdf". After several, they are
  "Summarize the new documents" and "Compare them". If nothing new was added, there
  are none.
- **Some messages are answered without the LLM.** If the Thread has no Documents yet,
  the bot replies "Upload a PDF first". "What can you do?" gets a fixed capabilities
  reply.

## Retrieval modes

- **Four Retrieval modes in the settings: `Auto` (default), `Full context`, `RAG`,
  `Agentic navigation`.** The user can switch mid-Thread, and the new mode applies
  from the next message. Each reply shows the Effective mode, for example
  `Mode: Auto → Agentic navigation`.
- **Every question covers all Documents in the Thread.** There is no Document picker.
- **Auto** estimates the tokens of the Thread's Documents (characters ÷ 4): 5k or
  less goes to Full context, and more goes to Agentic navigation. This way the default
  path shows the agent, and broad questions such as summaries work on large
  Documents. Auto never picks RAG.
- **Full context** sends the text of every Page. Above 100k tokens, it falls back to
  Agentic navigation and says so (`Full context → Agentic navigation (too large)`).
  That keeps it inside Haiku's cheaper price tier.
- **RAG** is only used when the user picks it, as the baseline to compare against.
  Search returns the top 8 Chunks by cosine similarity.
- **Agentic navigation is a LangGraph agent** with an agent node and a tool node. It
  has four tools:
  - `list_documents`
  - `get_outline`, which falls back to the first line of each Page when the PDF has
    no bookmarks
  - `read_pages`, about 10 Pages per call
  - `search`, the same Chunk search that RAG uses
- **The agent stops after 8 tool calls.** A counter in the graph state enforces this.
  When it is reached, the agent node runs once more without tools and answers from
  what it has read, adding "I stopped after 8 lookups; the answer may be incomplete".
  `recursion_limit` is set higher, as a safety net only.
- **The agent's work is visible.** Each tool call shows as a Chainlit Step through
  `LangchainCallbackHandler`, and the final answer streams token by token through
  `astream_events`.
- **Full context and RAG are plain code** on the `anthropic` SDK, with no framework.

## Answers

- **Every mode cites Pages in the same format:** `[invoice.pdf, p. 4]`, or
  `[invoice.pdf, pp. 4–5]` when a Chunk spans two Pages.
  - Full context and RAG use the Citations API on Page or Chunk blocks, so quotations
    are verbatim from the extracted text.
  - Agentic navigation writes `[name, p. N]` markers, as its prompt instructs, and
    code parses them.
- **Citations are shown the same way in every mode.** The answer text carries
  numbered markers such as `[1]`, and a Sources list at the end gives each one's
  Document, Pages and quoted text as Chainlit text elements. For the agent, the
  Sources list is attached after the Quote check.
- **Quote check for Agentic navigation:**
  - a quote is any text in double quotes of at least 5 words
  - before matching, whitespace is collapsed, case is ignored, words split by a
    hyphen at a line break are joined, and ligatures are unfolded
  - the quote is searched for on the cited Page first, then in the whole Document
  - a quote found on a different Page has its Citation corrected, and a quote not
    found at all is flagged ⚠️ "not found in invoice.pdf"
- **Answers come only from the Documents.** If they don't contain the answer, the bot
  says so and doesn't fall back to general knowledge.
- **History is limited to the last 10 turns.** Document text is reused across
  questions with prompt caching (`cache_control`).

## Models

- **The only backend is the Claude API**, with `ANTHROPIC_API_KEY` as the only
  secret. A Pro subscription doesn't cover API calls.
- **Default model is `claude-haiku-5-5`,** and `LLM_MODEL` overrides it. The
  `anthropic` client and LangGraph's `ChatAnthropic` share the same setting.
- **The app fails fast** if `ANTHROPIC_API_KEY` is missing.
- **Embeddings come from a local model** (`fastembed` with `BAAI/bge-small-en-v1.5`,
  English only). It is downloaded while the Docker image is built, so the first
  upload isn't slow and the app works offline.

## Ingestion

- **PyMuPDF does the text and Outline extraction.** Its AGPL licence is noted in the
  README.
- **Ingestion is synchronous.** The user waits and sees a "Processing…" step.
- **No limits** on file size, Page count or number of Documents.
- **Only the Text layer is used.** Tables come through as extracted text. Pages
  without a Text layer trigger a warning such as "Pages 3–12 have no text layer
  (scanned?); OCR isn't supported yet" and produce no Chunks. A PDF with no text at
  all is rejected.
- **Chunks follow the structure of the text.** The Document's text is joined and
  split by headings, then paragraphs, then sentences, into Chunks of about 800 tokens
  with about 100 tokens of overlap. PyMuPDF text blocks give the paragraphs, and font
  size is a rough way to spot headings. Chunks can cross Page breaks, so no context is
  lost there. Each Chunk records the `page_start` and `page_end` it spans, based on the
  character offset where each Page starts.
- **Upload checks:**
  - only `application/pdf` is accepted
  - encrypted or corrupted files get a clear error
  - a PDF that's already in the Thread is skipped, using a content hash

## Persistence

- **Postgres with Chainlit's built-in asyncpg data layer.** There is no custom
  storage code for chat history. Setting `DATABASE_URL` is what turns persistence
  on.
- **No LangGraph checkpointer.** Chat state comes from Chainlit's Threads, and
  Document state comes from our tables.
- **Database image: `pgvector/pgvector:pg18`.**
- **Schema written by hand in init scripts.** The Chainlit schema stays as it is. A
  second script adds the `vector` extension and the documents and chunks tables, and
  existing volumes need `docker compose down -v` once.
- **Document state is stored per Thread, not rebuilt.** On upload, metadata, the
  content hash, Page text, the Outline, Chunks and embeddings are saved under the
  Thread ID. On resume, they are loaded and the saved messages become the LLM
  history.
- **Deleting a Thread deletes its Documents.** The documents table has a foreign key
  to Chainlit's `"Thread"(id)` with `ON DELETE CASCADE`, and chunks cascade from
  documents. A single Document can't be removed yet.
- **Attachments are kept, on disk.** Chainlit only stores element bytes through a
  storage client, so without one a resumed Thread loses its PDF chips and the text of
  its Sources panels. A small custom storage client writes them to the named volume
  `attachments`. MinIO with Chainlit's S3 client was rejected: an extra container, and
  presigned URLs that the browser must be able to reach. Postgres `bytea` was rejected
  for its 1 GB cap per value. Documents stay text-only and don't link to their
  Attachment.
- **Attachments are served by a route that requires login.** PDFs open inline; other
  files download. There is no per-Thread check, since there is one demo account.
- **Chat history is kept by default.** It lives in the named volume `db-data`.

## Infrastructure

- **Docker Compose runs everything.**
- **`.env` is optional for tooling.** It is marked `required: false`, so test, lint
  and shell targets work without one. Running the app needs `ANTHROPIC_API_KEY`.

## Libraries

- **Runtime:**
  - `chainlit` for the UI
  - `asyncpg` and `pgvector` for Postgres
  - `anthropic` for Full context and RAG
  - `langgraph`, `langchain-anthropic` and `langchain-core` for Agentic navigation
  - `pymupdf` for extraction
  - `fastembed` for embeddings
  - `pydantic-settings` for config
- **Dev:** `pytest`, `pytest-asyncio`, `ruff`.
- **Not used:**
  - LangChain loaders, splitters and `PGVector`, because we own the schema and the
    chunking
  - SQLAlchemy and Alembic
  - a separate vector database
  - testcontainers

## Cleanup

- **The POC bot is removed.** `responder.py` and its tests go, and the project in
  `pyproject.toml` is renamed from `hello-world` to `pdf-chat`.

## Quality and deliverable

- **Unit tests wherever they make sense:** extraction, chunking and Page ranges, Auto
  routing, the Full context fallback, upload checks, the agent tools and tool-call
  cap, Citation parsing, the Quote check and the answer flow. They use a fake LLM (a
  fake Anthropic client, and a fake chat model for the graph) and fake embeddings.
- **One integration test runs against Postgres.** It is marked
  `@pytest.mark.integration`, run with `make test-integration`, and left out of
  `make test`. There are no LLM evals.
- **The test fixtures are generated with PyMuPDF and cover every PDF type:**
  - a small PDF (goes to Full context)
  - a large PDF (goes to Agentic navigation)
  - a PDF with an Outline
  - a scanned PDF with image-only Pages (the known gap)
- **The README compares the approaches:** the Retrieval modes, their trade-offs, why
  Auto prefers the agent for large Documents (slower and more expensive, but it
  handles broad questions), and why LangGraph is used only for the agent.
- **The README lists the follow-ups:**
  - OCR, or Claude's native PDF input
  - images and charts
  - background ingestion with progress
  - limits
  - removing a single Document
  - better retrieval: hybrid search with BM25, reranking, and contextual retrieval
- **The code should read as if a person wrote it,** with comments only where they're
  crucial.
