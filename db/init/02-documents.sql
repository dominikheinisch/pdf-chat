-- Documents uploaded into a Thread. Deleting the Thread (Chainlit deletes the row)
-- deletes its Documents too. Only the extracted text is kept, not the PDF.
--
-- Postgres runs this only when its data volume is empty: make reset to apply.

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
