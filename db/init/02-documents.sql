-- Documents uploaded into a Thread, and the Chunks they're searched by. Deleting
-- the Thread (Chainlit deletes the row) deletes both. Only the extracted text is
-- kept, not the PDF.
--
-- Postgres runs this only when its data volume is empty: make reset to apply.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id    TEXT NOT NULL REFERENCES "Thread" ("id") ON DELETE CASCADE,
    name         TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    -- One entry per page, in order; empty for pages without a text layer.
    pages        TEXT[] NOT NULL,
    outline      JSONB NOT NULL,
    tokens       INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (thread_id, content_hash)
);

-- No vector index: an exact scan is fast enough for a few thousand chunks.
CREATE TABLE chunks (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    page_start  INTEGER NOT NULL,
    page_end    INTEGER NOT NULL,
    -- BAAI/bge-small-en-v1.5
    embedding   VECTOR(384) NOT NULL
);

CREATE INDEX ON chunks (document_id);
