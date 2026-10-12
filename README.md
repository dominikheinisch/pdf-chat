# PDF chat

Upload PDFs into a chat and ask questions about them. Answers come only from the
documents and cite the page they came from. Built with Chainlit, the Claude API,
LangGraph and Postgres with pgvector.

## Run it

You need Docker and a Claude API key.

```sh
cp .env.example .env    # fill in ANTHROPIC_API_KEY, CHAINLIT_AUTH_SECRET, DEMO_PASSWORD
make run                # http://localhost:8001, log in with DEMO_USERNAME / DEMO_PASSWORD
```

Attach PDFs with the paperclip button at any point, then ask away. Pick a
**Retrieval mode** in the settings panel to compare approaches.

| Command                 | What it does                                         |
|-------------------------|------------------------------------------------------|
| `make test`             | Unit tests; no network, API key or database needed   |
| `make test-integration` | The Postgres store test, against the Compose database |
| `make lint`             | Ruff fix and format                                  |
| `make down`             | Stop; chats, documents and attachments are kept      |
| `make reset`            | Stop and delete all chats, documents and attachments |

The database schema lives in `db/init/` and only runs on an empty volume. After
changing it, or when upgrading from an older checkout, run `make reset` once.

Uploaded PDFs and the Sources panels are kept on the `attachments` volume, so a
resumed chat shows them as before. Chats from before that volume existed come back
without them; `make reset` clears them out.

## How it works

On upload, PyMuPDF extracts each page's text layer and the outline (bookmarks, or
the first line of each page when there are none). The text is split into chunks
along paragraphs and sentences, about 800 tokens with 100 tokens of overlap. Chunks
may cross page breaks and record the pages they span. They are embedded locally with
`BAAI/bge-small-en-v1.5`, and the page text, outline and chunks are stored per chat in
Postgres. Deleting a chat deletes its documents.

Each question then goes through one of four retrieval modes:

| Mode | How it answers | Good at | Weak at |
|---|---|---|---|
| **Full context** | Sends every page to Claude | Most complete answers, summaries, cross-references | Cost and latency grow with size; capped at 100k tokens |
| **RAG** | Sends the 8 chunks closest to the question | Cheap and fast; specific facts | Broad questions ("summarize this") see only 8 fragments |
| **Agentic navigation** | A LangGraph agent lists documents, reads outlines, reads page ranges and searches, up to 8 tool calls | Large documents, broad and multi-step questions | Slower and pricier; can stop before reading everything |
| **Auto** (default) | Full context up to 50k tokens, the agent above | Sensible without knowing the trade-offs | — |

**Why Auto prefers the agent over RAG for large documents.** The first thing people
ask about a long report is usually broad: "summarize it", "what are the key points?".
RAG can't answer that from 8 fragments, while the agent can read the outline and
then the sections that matter. That costs a few more calls and seconds per answer,
which is the right trade for the default. RAG stays available as the cheap baseline,
and Full context above 100k tokens also hands over to the agent, which keeps
requests inside Haiku's cheaper price tier.

**Why LangGraph only for the agent.** Full context and RAG are a single streamed API
call each; a framework would add layers without adding anything. The agent is a real
loop with tools, a call budget and a forced final answer, which is what LangGraph is
for. There is no LangGraph checkpointer: chat history comes from Chainlit's threads.

## Trusting the answers

- Every mode cites `[document, p. N]` (or `pp. N–M` for a chunk spanning a page
  break), shown as numbered markers with a Sources list.
- Full context and RAG use the Claude Citations API, so the quoted text is verbatim
  from the stored pages.
- The agent writes its own citations. Each quote of five or more words is checked
  against the stored page text, ignoring case, spacing, line-break hyphens and
  ligatures. A quote found on another page moves the citation there; a quote found
  nowhere is flagged with ⚠️.
- The prompts tell Claude to say so when the documents don't contain the answer,
  rather than falling back on general knowledge.

## Known gaps

- **Scanned pages** have no text layer and are skipped, with a warning naming them.
  A PDF with no text at all is rejected.
- **Images and charts** are ignored; tables come through as plain extracted text.
- **Retrieval is English-only** (the embedding model). Claude reads other languages,
  but search quality drops.
- **Vector search is an exact scan** with no index. That's fine for thousands of
  chunks, not millions.
- **Ingestion is synchronous** and there are no limits on size or count, so a huge
  upload keeps the user waiting.
- PyMuPDF is **AGPL**-licensed; a closed-source deployment would need its
  commercial licence or another extractor.

## Follow-ups

- OCR for scanned pages, or sending those pages to Claude's native PDF input
- Understanding images and charts
- Background ingestion with progress
- Limits on file size, page count and number of documents
- Removing a single document from a chat
- Better retrieval: hybrid search with BM25, a reranker, contextual retrieval
  (a line of context written in front of each chunk before embedding), and a vector
  index
- An eval set of questions per document type to compare the modes with numbers
