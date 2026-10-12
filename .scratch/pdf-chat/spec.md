# Spec: PDF chat

Status: ready-for-agent

Sources: `docs/pdf-chat-decisions.md` (all design decisions), `CONTEXT.md` (domain terms).
This spec uses the terms from `CONTEXT.md` (Thread, Document, Page, Text layer, Outline,
Chunk, Retrieval mode, Effective mode, Citation, Quote check).

## Problem Statement

A user has PDFs of very different size and quality, from a two-page invoice to a
300-page report, and sometimes scans with no text at all. They want to ask questions
about them in a chat and get answers they can trust. The answers should come only from
their PDFs, and they need to be able to check every claim against the Page it came
from. Today the repo has only a "hello world" placeholder with a Docker Compose
skeleton.

The task is also an interview exercise. The reviewer wants to see how the problem was
approached and which solutions were considered. So the app has to show and compare
more than one approach, not only answer questions.

## Solution

A Chainlit chat app with one demo login. In any Thread, the user attaches PDFs with
the paperclip button at any time. Each PDF is ingested into a Document: its Text layer
is extracted per Page, its Outline is read, and its text is split into Chunks that are
embedded and stored. The user then asks questions in the chat.

Every answer cites the Document and Page it came from and ends with a Sources list
that shows the quoted text. The bot answers only from the Thread's Documents and says
so when they don't contain the answer.

The user can choose from four Retrieval modes in the settings panel:

- **Auto** (default): Full context for small Documents (50k tokens or less), Agentic
  navigation for large ones.
- **Full context**: every Page goes to the model. Above 100k tokens it falls back to
  Agentic navigation.
- **RAG**: the top 8 Chunks by vector search, kept as a baseline to compare against.
- **Agentic navigation**: a LangGraph agent that lists Documents, reads Outlines,
  reads Page ranges and searches Chunks, with every tool call shown as a Step.

Each reply shows its Effective mode. Threads, their messages and their Documents
persist in Postgres and come back when a Thread is resumed.

The README explains the approaches, their trade-offs and the follow-ups.

## User Stories

### Access and Threads

1. As a user, I want to log in with the demo account, so that my Threads are saved
   under one identity.
2. As a user, I want a wrong username or password to be rejected without revealing
   which one was wrong, so that the login behaves like a real one.
3. As a user, I want to see my previous Threads in the sidebar, so that I can return
   to earlier work.
4. As a user, I want to resume a Thread and keep asking about its Documents without
   uploading them again, so that my work survives a restart.
5. As a user, I want a resumed Thread to remember the earlier questions and answers,
   so that follow-up questions still make sense.
6. As a user, I want deleting a Thread to delete its Documents as well, so that
   nothing I removed stays behind.
7. As a user, I want my Threads to survive `make down` and a restart, so that I don't
   lose history while developing.

### Uploading

8. As a user, I want starters that tell me to upload a PDF and explain what the bot
   can do, so that I know how to begin.
9. As a user, I want to attach a PDF at any point in a Thread, so that I can add
   material as the conversation goes on.
10. As a user, I want to attach several PDFs in one message, so that I can load a set
    of related Documents at once.
11. As a user, I want to see a Processing step for each PDF, so that I know the app
    is working on large files.
12. As a user, I want a summary such as "Added 3 Documents (1 skipped as duplicate)"
    after an upload, so that I know what happened to each file.
13. As a user, I want a PDF that's already in the Thread to be skipped, so that
    duplicates don't distort answers.
14. As a user, I want files that aren't PDFs to be refused with a clear message, so
    that I understand why nothing happened.
15. As a user, I want encrypted or corrupted PDFs to get a clear error, so that I know
    to fix the file.
16. As a user, I want a warning that names the Pages without a Text layer, for
    example "Pages 3–12 have no text layer (scanned?); OCR isn't supported yet", so
    that I know which parts the bot can't see.
17. As a user, I want a PDF with no text at all to be rejected with an explanation, so
    that I don't ask questions the bot can't answer.
18. As a user, I want no limit on file size, Page count or number of Documents, so
    that large reports work too.
19. As a user, I want quick replies that name the Document I just uploaded, such as
    "Summarize invoice.pdf" and "Key points of invoice.pdf", so that I can start with
    one click.
20. As a user, I want quick replies such as "Summarize the new documents" and "Compare
    them" after uploading several Documents, so that I can work with the set.
21. As a user, I want no quick replies when nothing new was added, so that I'm not
    offered actions that make no sense.

### Asking questions

22. As a user, I want to be told "Upload a PDF first" when I ask something before
    uploading, so that I know what's missing.
23. As a user, I want "What can you do?" to explain the bot's capabilities, so that I
    can learn the features.
24. As a user, I want each question to cover all Documents in the Thread, so that I
    don't have to say which one I mean.
25. As a user, I want answers to stream, so that I can start reading straight away.
26. As a user, I want the bot to say when my Documents don't contain the answer, so
    that it doesn't guess from general knowledge.
27. As a user, I want follow-up questions to use the recent conversation, so that I
    can say "and what about the second clause?".
28. As a user, I want long Threads to stay fast and affordable, so that only the
    recent conversation is sent each time and the Document text is reused from the
    cache.

### Retrieval modes

29. As a user, I want to choose the Retrieval mode in the settings panel, so that I
    can compare the approaches.
30. As a user, I want Auto to be the default, so that I get a sensible choice without
    knowing the trade-offs.
31. As a user, I want Auto to send small Documents to Full context, so that short
    files get the most complete answers.
32. As a user, I want Auto to send large Documents to Agentic navigation, so that
    broad questions such as summaries still work on long reports.
33. As a user, I want Auto to look again after every upload, so that the choice
    follows the Thread's current size.
34. As a user, I want Full context to fall back to Agentic navigation above 100k
    tokens and tell me so, so that the cost stays low and I understand why.
35. As a user, I want to be able to pick RAG explicitly, so that I can compare it with
    the other modes.
36. As a user, I want to switch the Retrieval mode mid-Thread, with the new one
    applying from my next message, so that I can try the same question in several
    modes.
37. As a user, I want each reply to show its Effective mode, for example `Auto →
    Agentic navigation`, so that I know which approach produced the answer.

### Agentic navigation

38. As a user, I want the agent to look at the Documents and their Outlines before
    reading, so that it reads the relevant sections.
39. As a user, I want the agent to be able to read ranges of Pages, so that it can
    summarise and follow arguments across Pages.
40. As a user, I want the agent to be able to search Chunks, so that it can find
    specific facts quickly.
41. As a user, I want an Outline even for PDFs without bookmarks, built from the
    first line of each Page, so that the agent can still find its way.
42. As a user, I want to see each tool call as a Step, so that I can follow how the
    agent reached its answer.
43. As a user, I want the agent to stop after 8 lookups and answer with what it has,
    with a note that the answer may be incomplete, so that I always get an answer in
    reasonable time.
44. As a user, I want the agent's final answer to stream, so that it feels as
    responsive as the other modes.

### Citations and trust

45. As a user, I want every answer to cite the Document and Page, for example
    `[invoice.pdf, p. 4]`, so that I can check it.
46. As a user, I want a Citation to show a Page range such as `pp. 4–5` when the text
    spans a Page break, so that the reference is exact.
47. As a user, I want numbered markers in the answer and a Sources list with the
    quoted text, so that I can check claims without opening the PDF.
48. As a user, I want citations to look the same in every Retrieval mode, so that
    comparing modes is fair.
49. As a user, I want quotes in agent answers to be checked against the stored text,
    so that misquotes are caught.
50. As a user, I want a quote that sits on a different Page than cited to get its
    Citation corrected, so that the reference I follow is right.
51. As a user, I want a quote that isn't found at all to be flagged with ⚠️, so that I
    know not to trust it.

### Operator and reviewer

52. As an operator, I want the app to refuse to start without `ANTHROPIC_API_KEY`, so
    that a misconfiguration shows up immediately.
53. As an operator, I want to change the model with `LLM_MODEL`, so that I can trade
    cost for quality without code changes.
54. As an operator, I want the embedding model to be included in the image, so that
    the first upload isn't slow and embeddings work offline.
55. As an operator, I want one `make` command to start the app and its database, so
    that setup is trivial.
56. As an operator, I want test, lint and shell targets to work without a `.env`, so
    that tooling never needs secrets.
57. As an operator, I want `.env` to be ignored by git, so that secrets aren't
    committed.
58. As a developer, I want unit tests that run without network, API keys or a
    database, so that `make test` is fast and reliable.
59. As a developer, I want one integration test against real Postgres, run separately
    with `make test-integration`, so that the storage layer is proven.
60. As a reviewer, I want a README that compares the Retrieval modes and explains why
    Auto prefers the agent for large Documents, so that I understand the reasoning.
61. As a reviewer, I want the README to list known gaps and follow-ups, so that I can
    see the next steps were considered.
62. As a reviewer, I want the code to read as if a person wrote it, so that it's easy
    to review.

## Implementation Decisions

### How the work is done

- **The work starts from the `chat` branch as it is.** That means the hello-world
  placeholder plus the Docker Compose, Dockerfile and Makefile skeleton. The
  `chainlit-example` branch is reference material only. Its code may be reused and
  adapted (the demo auth, the Chainlit Postgres schema script, the Compose database
  service, the Makefile changes), but its commits are not cherry-picked, merged or
  rebased. The work is built up in small conventional commits, as if written from
  scratch.
- **The hello-world placeholder and its test are removed,** and the project is
  renamed from `hello-world` to `pdf-chat`. The container command changes to running
  Chainlit headless on port 8000, published on loopback only.
- **`.env` is added to `.gitignore`.** An `.env.example` lists `ANTHROPIC_API_KEY`,
  `LLM_MODEL` (optional), `CHAINLIT_AUTH_SECRET`, `DEMO_USERNAME`, `DEMO_PASSWORD`
  and `APP_PORT` (optional).

### Modules

- **Config:** settings from the environment through `pydantic-settings`. It fails at
  startup without `ANTHROPIC_API_KEY`. The model defaults to `claude-haiku-5-5`. It
  also holds the demo credentials and the database URL. The thresholds (50k for
  Auto, 100k for Full context, 8 tool calls, top 8 Chunks, 10 turns of history) are
  named constants, not settings.
- **Extraction (deep module, pure):** takes PDF bytes and a file name and returns a
  Document draft: a content hash, the text of each Page, the Pages without a Text
  layer, and the Outline. The Outline comes from the bookmarks, or from the first
  line of each Page when there are none. Errors are typed: not a PDF, encrypted,
  corrupted, no text at all. It uses PyMuPDF.
- **Chunking (deep module, pure):** takes the Page texts and returns Chunks, each
  with its text, `page_start` and `page_end`.
  - The Document's text is joined, and the character offset where each Page starts
    is recorded.
  - The text is split by headings, then paragraphs, then sentences, aiming for about
    800 tokens per Chunk with about 100 tokens of overlap. Tokens are estimated as
    characters ÷ 4.
  - Paragraphs come from PyMuPDF text blocks, and a larger font size is a rough sign
    of a heading.
  - Chunks may cross Page breaks. Pages without a Text layer add nothing.
- **Embedder:** a small interface with two operations, embed passages and embed a
  query. The real implementation is `fastembed` with `BAAI/bge-small-en-v1.5` (384
  dimensions, English), and the model is downloaded while the image is built.
- **Document store:** an interface with these operations:
  - add a Document, with its Pages, Outline, Chunks and embeddings, to a Thread
  - check whether the Thread already has a given content hash
  - list the Thread's Documents with their estimated token counts
  - get a Document's Outline
  - read a range of Pages
  - read all Pages of the Thread
  - search the Thread's Chunks by vector

  There is a Postgres implementation on asyncpg with pgvector, and an in-memory one
  for tests.
- **Retrieval mode routing (pure):** takes the selected Retrieval mode and the
  Thread's estimated token total, and returns the Effective mode plus a label such
  as `Auto → Agentic navigation` or `Full context → Agentic navigation (too large)`.
- **Full context and RAG answerers:** plain `anthropic` SDK calls with streaming.
  - Full context sends one document block per Page. RAG sends one document block
    per retrieved Chunk, titled with the Document name and Page range.
  - Citations are turned on, and `cache_control` is set on the document content.
  - The system prompt says to answer only from the documents, and to say so when
    they don't contain the answer.
  - Citation results are mapped back to the Document and Page or Page range.
- **Agentic navigation answerer:** a LangGraph graph with an agent node and a tool
  node, using `ChatAnthropic` with the same model setting.
  - Tools: `list_documents`, `get_outline`, `read_pages` (about 10 Pages per call)
    and `search` (the same Chunk search RAG uses). Every tool is limited to the
    current Thread.
  - The graph state counts tool calls. At 8, the agent node runs once more with no
    tools bound and appends "I stopped after 8 lookups; the answer may be
    incomplete". `recursion_limit` is set higher, as a safety net only.
  - The prompt makes the agent write Citations as `[name, p. N]` or
    `[name, pp. N–M]`.
  - The final answer is streamed from `astream_events`, and tool calls appear as
    Chainlit Steps through `LangchainCallbackHandler`.
- **Citation parsing and Quote check (deep module, pure):** takes the agent's answer
  text and the Thread's Page texts.
  - It parses the `[name, p. N]` markers and turns them into numbered markers with a
    Sources list.
  - It finds quotes, meaning text in double quotes of at least 5 words.
  - Both sides are normalised: whitespace collapsed, case ignored, words split by a
    hyphen at a line break joined, ligatures unfolded.
  - Each quote is searched for on the cited Page, then in the whole Document. A
    quote found on another Page has its Citation corrected, and a quote not found is
    flagged ⚠️ "not found in <name>".
- **App core (the main seam):** two operations, with the Anthropic client, the chat
  model, the Embedder and the Document store passed in.
  - `ingest(thread, uploaded files)` checks the type, runs extraction, skips
    duplicates by content hash, chunks and embeds, and stores. It returns each
    file's outcome (added, skipped or rejected with a reason), the warnings about
    Pages without a Text layer, the summary line and the quick replies.
  - `ask(thread, question, selected Retrieval mode, history)` returns an async
    stream of events: the Effective mode label, Step start and end events for tool
    calls, answer tokens, and the final Sources.
  - Fixed replies come out of `ask` without any LLM call: "Upload a PDF first" when
    the Thread has no Documents, and the capabilities text for "What can you do?".
  - History is cut to the last 10 turns.
- **Chainlit handlers (thin, no logic):**
  - password auth that compares both fields with a constant-time comparison
  - starters
  - the settings panel with the four Retrieval modes, Auto by default
  - `spontaneous_file_upload` restricted to `application/pdf`
  - chat start and resume, where resume loads the saved messages as history
  - message handling that turns the app core's events into Steps, a streamed
    message, the mode label, text elements for the Sources list and quick-reply
    actions
  - a quick-reply action callback that posts the clicked text as the user's message
    and answers it

### Schema and persistence

- **Postgres runs from the `pgvector/pgvector:pg18` image** with dev-only
  credentials, a healthcheck, no published port, and a named volume `db-data`. The
  app starts once the database is healthy and gets `DATABASE_URL`, which turns on
  Chainlit's asyncpg data layer.
- **Init script 1** is the Chainlit schema, written by hand. The POC's version can be
  reused.
- **Init script 2** adds the `vector` extension and two tables:
  - **documents:** id, Thread id (foreign key to Chainlit's `"Thread"(id)`
    `ON DELETE CASCADE`), name, content hash (unique per Thread), page count, token
    estimate, Outline as JSON, Page texts as an ordered text array or JSON, the Pages
    without a Text layer, and a creation time
  - **chunks:** id, Document id (foreign key `ON DELETE CASCADE`), position, text,
    `page_start`, `page_end`, and a 384-dimension embedding
- **Searches use exact cosine distance.** No vector index is added, which is fine at
  this scale and noted in the README.
- **Attachments are stored on the `attachments` volume** (see `.scratch/attachments/spec.md`). Documents keep only text.
- **There is no LangGraph checkpointer.** Messages come from Chainlit's Thread, and
  Document state comes from the tables above.

### Dependencies

- **Runtime:** `chainlit`, `asyncpg`, `pgvector`, `anthropic`, `langgraph`,
  `langchain-anthropic`, `langchain-core`, `pymupdf`, `fastembed`,
  `pydantic-settings`.
- **Dev:** `pytest`, `pytest-asyncio`, `ruff`.

### Build and Makefile

- **`run`** starts the app and database (`docker compose up --build`), with the UI on
  loopback port `APP_PORT`, default 8001.
- **The tool targets** (`test`, `lint`, `shell`) run without the database and
  without a `.env`.
- **`test`** excludes integration tests, and a new **`test-integration`** target
  starts the database and runs only the tests marked `integration`.
- **`down`** keeps the data volume. Wiping it is a separate documented step, which
  is needed once after a schema change.

### Code style

- **Plain, idiomatic Python** with small functions, clear names and type hints.
- **Comments only where something isn't obvious**, for example why Chunks may cross
  Page breaks, or why there's a cap on tool calls.

## Testing Decisions

- **Good tests check behaviour you can see from outside:** what `ingest` and `ask`
  return or emit for a given input, and what the pure modules return. They don't
  assert on internal calls, prompt wording or graph structure. Fakes stand in only
  at the four boundaries passed into the app core.
- **Seam 1, the app core (most tests):** these use a fake Anthropic client that
  streams scripted text with citations, a fake LangGraph chat model with scripted
  tool calls and a final answer, fake deterministic embeddings, and the in-memory
  Document store. They cover:
  - Auto routing at the 50k boundary and the Full context fallback above 100k, with
    the right Effective mode labels
  - outcomes when uploading several files: added, skipped as duplicate, rejected as
    not a PDF, encrypted, corrupted, or without text
  - warnings about Pages without a Text layer
  - which quick replies are offered for one new Document, several, or none
  - "Upload a PDF first" and the capabilities reply, both without any LLM call
  - history cut to 10 turns
  - the agent stopping after 8 tool calls and still answering, with the note
  - Sources in the same shape in every mode
- **Seam 2, the Postgres Document store (one integration test):** it adds a Document
  to a Thread, reads its Pages and Outline back, runs a vector search that returns
  the closest Chunk with its Page range, rejects a duplicate content hash, and checks
  that deleting the Thread removes its Documents and Chunks. It is marked
  `integration` and uses the Compose database. It doesn't use testcontainers.
- **Seam 3, the pure modules tested directly:**
  - extraction: Page texts, the Outline from bookmarks and the fallback Outline,
    Pages without a Text layer, and the error types
  - chunking: Chunks within their size, overlap, Page ranges for Chunks crossing a
    Page break, and Pages without a Text layer skipped
  - Citation parsing and Quote check: an exact match, a match only after
    normalisation, a correction to another Page, a ⚠️ flag, and short quotes ignored
- **The Chainlit handlers have no tests.** They are kept too thin to need them.
- **The fixtures are generated in code with PyMuPDF** when the tests run. Nothing
  binary is committed. The fixtures are:
  - a small PDF that goes to Full context
  - a large PDF that goes to Agentic navigation
  - a PDF with bookmarks
  - a PDF whose Pages are images only, standing in for a scan
- **There are no LLM evals and no tests that call the real API.**
- **Prior art:** the single hello-world pytest test on this branch, which is removed.
  The POC's responder tests on `chainlit-example` are a style reference (plain pytest
  functions, no classes).

## Out of Scope

- OCR, or using Claude's native PDF input for scanned Pages
- understanding images and charts
- ingestion in the background with progress
- limits on file size, Page count or number of Documents
- removing a single Document from a Thread
- hybrid search with BM25, reranking, contextual retrieval, and a vector index
- languages other than English for retrieval
- several users, sign-up, or roles
- a Claude Code or Agent SDK backend, or any provider other than the Claude API
- LLM evals

## Further Notes

- **The README must cover:**
  - setup: `.env`, `make run`, the login
  - the four Retrieval modes and their trade-offs
  - why Auto prefers Agentic navigation for large Documents (slower and more
    expensive, but it handles broad questions)
  - why LangGraph is used only for the agent
  - PyMuPDF's AGPL licence
  - the Postgres volume reset after schema changes
  - the follow-ups listed under Out of Scope
- **Cost:** Full context is capped at 100k tokens to stay in Haiku's cheaper price
  tier, and prompt caching makes repeated questions about the same Documents cheap.
- **Commits** follow the repo rules: Conventional Commits, one line, no body and no
  trailers.
