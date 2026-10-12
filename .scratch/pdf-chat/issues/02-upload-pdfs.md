# 02 — Upload PDFs into a Thread

**What to build:** At any point in a Thread, the user attaches one or more PDFs with
the paperclip button. Each PDF gets its own "Processing…" step, and a summary line
follows, such as "Added 2 Documents (1 skipped as duplicate)". Bad files get clear
messages, and Pages without a Text layer are named in a warning. Documents are stored
per Thread: Pages, Outline, content hash and a token estimate, but no Chunks yet. They
come back when the Thread is resumed, and deleting the Thread removes them. The
original PDF bytes are never stored. See the spec at `.scratch/pdf-chat/spec.md`.

**Blocked by:** 01 — App skeleton

**Status:** ready-for-agent

- [ ] Spontaneous upload is on and accepts only `application/pdf`. Anything else is refused with a message.
- [ ] A pure extraction module turns PDF bytes into Page texts, the Pages without a Text layer, the Outline (from bookmarks, or the first line of each Page as a fallback) and a content hash. It raises typed errors for not a PDF, encrypted, corrupted, and no text at all.
- [ ] Encrypted and corrupted PDFs get a clear error, and a PDF with no text at all is rejected with an explanation.
- [ ] Pages without a Text layer give a warning such as "Pages 3–12 have no text layer (scanned?); OCR isn't supported yet".
- [ ] A PDF whose content hash is already in the Thread is skipped.
- [ ] The app core's `ingest` returns each file's outcome (added, skipped, or rejected with a reason), the warnings and the summary line.
- [ ] A Document store interface has a Postgres implementation and an in-memory one. A second init script adds the `vector` extension and a documents table with a cascading foreign key to Chainlit's Thread and a content hash that's unique per Thread.
- [ ] Resuming a Thread makes its Documents available again without uploading.
- [ ] Deleting a Thread deletes its Documents.
- [ ] Test fixtures are generated in code with PyMuPDF: a small PDF, a PDF with bookmarks, and a PDF of images only. No binary files are committed.
- [ ] Unit tests cover the extraction module and `ingest` outcomes with the in-memory store.
- [ ] One integration test, marked `integration` and run by a new `make test-integration` target, covers the Postgres store: adding and reading back a Document, rejecting a duplicate hash, and the cascade delete. `make test` leaves it out.
