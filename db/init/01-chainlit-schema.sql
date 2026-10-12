-- Tables Chainlit's built-in Postgres data layer (chainlit.data.chainlit_data_layer)
-- reads and writes. Types follow the Prisma schema in Chainlit/chainlit-datalayer;
-- names are quoted because the queries use camelCase identifiers.
--
-- Postgres runs this only when its data volume is empty. After editing it, wipe
-- the volume to apply: docker compose down -v

CREATE TYPE "StepType" AS ENUM (
    'assistant_message', 'embedding', 'llm', 'retrieval', 'rerank',
    'run', 'system_message', 'tool', 'undefined', 'user_message'
);

CREATE TABLE "User" (
    "id"         TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "metadata"   JSONB NOT NULL,
    "identifier" TEXT NOT NULL UNIQUE
);

CREATE TABLE "Thread" (
    "id"        TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "name"      TEXT,
    "metadata"  JSONB NOT NULL,
    "tags"      TEXT[] DEFAULT ARRAY[]::TEXT[],
    "userId"    TEXT REFERENCES "User" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE "Step" (
    "id"        TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "parentId"  TEXT REFERENCES "Step" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    "threadId"  TEXT REFERENCES "Thread" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    "input"     TEXT,
    "metadata"  JSONB NOT NULL,
    "name"      TEXT,
    "output"    TEXT,
    "type"      "StepType" NOT NULL,
    "showInput" TEXT DEFAULT 'json',
    "isError"   BOOLEAN DEFAULT false,
    "startTime" TIMESTAMP(3) NOT NULL,
    "endTime"   TIMESTAMP(3) NOT NULL,
    -- Added after the Prisma schema froze; see docs.chainlit.io/guides/migration/
    -- 2.1.0, 2.3.0 and 2.9.4. Chainlit 2.12's asyncpg layer doesn't write them yet.
    "command"     TEXT,
    "defaultOpen" BOOLEAN,
    "modes"       JSONB
);

CREATE TABLE "Element" (
    "id"          TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "threadId"    TEXT REFERENCES "Thread" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    "stepId"      TEXT NOT NULL REFERENCES "Step" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    "metadata"    JSONB NOT NULL,
    "mime"        TEXT,
    "name"        TEXT NOT NULL,
    "objectKey"   TEXT,
    "url"         TEXT,
    "chainlitKey" TEXT,
    "display"     TEXT,
    "size"        TEXT,
    "language"    TEXT,
    "page"        INTEGER,
    "props"       JSONB
);

CREATE TABLE "Feedback" (
    "id"        TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "stepId"    TEXT REFERENCES "Step" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    "name"      TEXT NOT NULL,
    "value"     DOUBLE PRECISION NOT NULL,
    "comment"   TEXT
);

-- Sidebar: a user's threads, newest first.
CREATE INDEX ON "Thread" ("userId", "updatedAt");
-- Resume: a thread's steps in order.
CREATE INDEX ON "Step" ("threadId", "startTime");
CREATE INDEX ON "Step" ("parentId");
CREATE INDEX ON "Element" ("threadId");
CREATE INDEX ON "Element" ("stepId");
CREATE INDEX ON "Feedback" ("stepId");
