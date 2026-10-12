# 03 — Full context answers with Citations

**What to build:** Questions about the Thread's Documents get streamed answers based
on the text of every Page. Every answer cites `[name, p. N]` as numbered markers and
ends with a Sources list giving each Document, Page and quoted text. The bot answers
only from the Documents and says so when they don't contain the answer. After an
upload, quick replies name the new Documents, and clicking one asks that question.
Each reply shows `Mode: Full context`. See the spec at `.scratch/pdf-chat/spec.md`.

**Blocked by:** 02 — Upload PDFs into a Thread

**Status:** ready-for-agent

- [ ] The Full context answerer uses the `anthropic` SDK with streaming, one document block per Page, Citations turned on, and `cache_control` on the document content.
- [ ] The system prompt makes the model answer only from the Documents and say when they don't cover the question.
- [ ] Citation results are mapped to a Document and Page and shown as numbered markers plus a Sources list of Chainlit text elements.
- [ ] Every question covers all Documents in the Thread.
- [ ] History is the last 10 turns. On resume, it comes from the Thread's saved messages.
- [ ] `ask` emits a stream of events: the mode label, answer tokens and the final Sources. The handlers only render them.
- [ ] Quick replies after one new Document: "Summarize <name>" and "Key points of <name>". After several: "Summarize the new documents" and "Compare them". When nothing new was added: none.
- [ ] Clicking a quick reply posts its text as the user's message and answers it.
- [ ] Unit tests use a fake Anthropic client that streams scripted text with citations, and cover the Sources shape, the cut to 10 turns and the quick-reply rules.
