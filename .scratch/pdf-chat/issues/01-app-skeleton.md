# 01 — App skeleton: login, Threads saved in Postgres, replies without the LLM

**What to build:** `make run` starts the Chainlit app and Postgres. The user logs in
with the demo account, sees PDF-focused starters, and gets a fixed reply: "Upload a PDF
first" when the Thread has no Documents, or the capabilities text for "What can you
do?". The Thread appears in the sidebar and is still there after a restart. Build it
from scratch on this branch. Code on `chainlit-example` may be reused and adapted, but
its commits must not be cherry-picked, merged or rebased. See the spec at
`.scratch/pdf-chat/spec.md`.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The hello-world placeholder and its test are removed, and the project is renamed to `pdf-chat`.
- [ ] `.env` is git-ignored. `.env.example` lists `ANTHROPIC_API_KEY`, `LLM_MODEL` (optional), `CHAINLIT_AUTH_SECRET`, `DEMO_USERNAME`, `DEMO_PASSWORD` and `APP_PORT` (optional).
- [ ] Config is loaded with `pydantic-settings`. The app refuses to start without `ANTHROPIC_API_KEY`, and the model defaults to `claude-haiku-5-5`.
- [ ] Compose runs a `pgvector/pgvector:pg18` database with a healthcheck, no published port and the `db-data` volume. The app waits for it to be healthy and gets `DATABASE_URL`.
- [ ] A hand-written init script creates the Chainlit schema, and Chainlit's asyncpg data layer saves Threads.
- [ ] The UI is published on loopback only, on `APP_PORT` (default 8001), and Chainlit runs headless.
- [ ] Password auth checks the demo account with a constant-time comparison on both fields.
- [ ] Starters: "Upload a PDF to begin" and "What can you do?".
- [ ] An app core with an `ask` operation returns the fixed replies without any LLM call. The Chainlit handlers stay thin.
- [ ] Unit tests cover both fixed replies through `ask`.
- [ ] The Makefile `run` target starts the app and the database. `test`, `lint` and `shell` work without the database and without a `.env`. `down` keeps the data volume.
