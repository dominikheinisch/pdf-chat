# 04 — RAG mode with structure-aware Chunks

**What to build:** The settings panel offers the Retrieval modes Full context and RAG,
and the choice applies from the next message. Ingestion now also splits each Document
into Chunks along its structure, records the Pages each Chunk spans, embeds the Chunks
locally and stores them. In RAG, answers use the top 8 Chunks and cite Page ranges
such as `[report.pdf, pp. 4–5]`, in the same Sources format as Full context. See the
spec at `.scratch/pdf-chat/spec.md`.

**Blocked by:** 03 — Full context answers with Citations

**Status:** ready-for-agent

- [ ] A settings panel lets the user choose the Retrieval mode. Changing it mid-Thread applies from the next message and survives resume.
- [ ] A pure chunking module joins the Page texts and splits them by headings, then paragraphs, then sentences, into Chunks of about 800 tokens (characters ÷ 4) with about 100 tokens of overlap. Each Chunk has `page_start` and `page_end` and may cross a Page break. Pages without a Text layer add nothing.
- [ ] An Embedder interface (embed passages, embed a query) is implemented with `fastembed` and `BAAI/bge-small-en-v1.5`. The model is downloaded during the image build.
- [ ] A chunks table stores the Chunk text, position, Page range and a 384-dimension embedding, and cascades from documents. Search uses exact cosine distance with no index.
- [ ] The RAG answerer sends one document block per retrieved Chunk, titled with the Document name and Page range, with Citations and the same prompt rules as Full context.
- [ ] Each reply shows `Mode: RAG` or `Mode: Full context`.
- [ ] A large PDF fixture is generated in code.
- [ ] Unit tests cover chunking (size, overlap, Page ranges across a break, Pages without a Text layer) and a RAG answer through `ask` with fake embeddings.
- [ ] The Postgres integration test also covers a vector search that returns the closest Chunk with its Page range.
