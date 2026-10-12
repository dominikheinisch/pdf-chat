# PDF chat

A chat app where a user uploads PDFs into a chat and asks questions that are answered
only from those PDFs, with page citations.

## Language

**Thread**:
One chat with its own messages and Documents.
_Avoid_: Conversation, session, chat

**Document**:
An uploaded PDF after ingestion, owned by exactly one Thread.
_Avoid_: File, PDF (once ingested)

**Page**:
One page of a Document, the unit every citation points to.

**Text layer**:
The extractable text of a Page. A Page without it (for example a scan) contributes nothing.

**Outline**:
A Document's table of contents, taken from its bookmarks or derived from its Pages.

**Chunk**:
A slice of a Document's text used for search. It follows headings and paragraphs, can
cross a Page break, and records the range of Pages it spans.

**Retrieval mode**:
How a Thread's Documents are put in front of the model: Auto, Full context, RAG or
Agentic navigation. Chosen by the user.
_Avoid_: Strategy, mode (alone)

**Effective mode**:
The Retrieval mode that actually answered a message, after Auto's choice or a fallback.

**Citation**:
A reference from an answer to a Document and Page, written as `[name, p. N]`.

**Quote check**:
Verifying that text an answer quotes really appears in the cited Document.
