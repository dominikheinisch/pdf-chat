# 08 — README

**What to build:** A README that lets a reviewer run the app and understand how it
works and why. It also shows which solutions were considered, as the interview task
asks. See the spec at `.scratch/pdf-chat/spec.md` and `docs/pdf-chat-decisions.md`.

**Blocked by:** 06 — Quote check for agent answers, 07 — Auto mode and the Full context fallback

**Status:** ready-for-agent

- [ ] Setup: copying `.env.example`, `make run`, the demo login, `make test` and `make test-integration`.
- [ ] The four Retrieval modes with their trade-offs (quality, latency, cost), and how Auto chooses between them.
- [ ] Why Auto prefers Agentic navigation for large Documents, and why RAG stays as a baseline.
- [ ] Why LangGraph is used only for the agent, while Full context and RAG are plain SDK code.
- [ ] How citations and the Quote check make answers verifiable.
- [ ] Known gaps: scanned Pages, images and charts, retrieval in English only, and exact vector search with no index (fine at this scale).
- [ ] Ops notes: PyMuPDF is AGPL, and the database volume must be reset after a schema change.
- [ ] Follow-ups:
  - OCR, or Claude's native PDF input
  - images and charts
  - background ingestion with progress
  - limits
  - removing a single Document
  - hybrid search with BM25, reranking and contextual retrieval
  - a vector index
- [ ] The README is concise and written in plain prose.
