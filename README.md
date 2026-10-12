# PDF chat

Upload PDFs into a chat and ask questions about them. Answers come only from the
documents and cite the page they came from. Built with Chainlit, the Claude API,
LangGraph and Postgres with pgvector.

## How it works

On upload, PyMuPDF extracts each page's text layer and the outline (bookmarks, or
the first line of each page when there are none). The text is split into chunks
along paragraphs and sentences, about 800 tokens with 100 tokens of overlap. Chunks
may cross page breaks and record the pages they span. They are embedded locally with
`BAAI/bge-small-en-v1.5`, and the page text, outline and chunks are stored per chat in
Postgres.

Each question then goes through one of four retrieval modes, picked in the settings
panel:

| Mode | How it answers | Good at | Weak at |
|---|---|---|---|
| **Full context** | Sends every page to Claude | Most complete answers, summaries, cross-references | Cost and latency grow with size; capped at 100k tokens, then the agent |
| **RAG** | Sends the 8 chunks closest to the question | Cheap and fast; specific facts | Broad questions ("summarize this") see only 8 fragments |
| **Agentic navigation** | A LangGraph agent lists documents, reads outlines, reads page ranges and searches, up to 8 tool calls | Large documents, broad and multi-step questions | Slower and pricier; can stop before reading everything |
| **Auto** (default) | Full context up to 5k tokens, the agent above | Sensible without knowing the trade-offs | — |

- **Auto picks the agent over RAG for large documents**: first questions are usually
  broad ("summarize it"), and 8 fragments can't answer those.
- **LangGraph is used only for the agent**: Full context and RAG are a single API call
  each, while the agent is a loop with tools.

## Trusting the answers

- Every mode cites, shown as numbered markers with a Sources list.
- Full context and RAG use the Claude Citations API, so the quoted text is verbatim
  from the stored pages.
- The agent writes its own citations, so its quotes are checked against the pages:
  a wrong page is corrected, a quote found nowhere is flagged.
- The prompts tell Claude to say so when the documents don't contain the answer,
  rather than falling back on general knowledge.

## Gaps and follow-ups

- **One demo account**, documents scoped by chat only → a user ID on documents and
  attachments.
- **Scanned pages** are skipped → OCR, or Claude's native PDF input for those pages.
- **Images and charts** are ignored, tables are plain text → a layout-aware parser,
  vision captions.
- **Retrieval is English-only** → multilingual embeddings.
- **Vector search is an exact scan** → a vector index, plus hybrid search with BM25, a
  reranker and contextual retrieval.
- **Ingestion is synchronous**, with no cap on pages or tokens → background ingestion
  with progress, limits on size, pages and document count.
- **Questions and document text go to the Anthropic API** → a local or EU-hosted LLM.
  Full context and RAG rely on the Claude Citations API, so they would need another
  way to cite.
- **PyMuPDF is AGPL**-licensed.
- Also: a summarize tool for the agent or per-document summaries cached at upload,
  removing a single document from a chat, and an eval set of questions per document
  type to compare the modes with numbers.

## Run it

You need Docker and a Claude API key.

```sh
cp .env.example .env    # fill in ANTHROPIC_API_KEY, CHAINLIT_AUTH_SECRET, DEMO_PASSWORD
make run                # http://localhost:8001, log in with DEMO_USERNAME / DEMO_PASSWORD
```

| Command                 | What it does                                         |
|-------------------------|------------------------------------------------------|
| `make test`             | Unit tests; no network, API key or database needed   |
| `make test-integration` | The Postgres store test, against the Compose database |
| `make lint`             | Ruff fix and format                                  |
| `make down`             | Stop; chats, documents and attachments are kept      |
| `make reset`            | Stop and delete all chats, documents and attachments |
