# 01 — Persist Attachments across restarts and resumed Threads

**What to build:** A resumed Thread looks like the live one. Today Chainlit has no
storage client, so it saves `Element` rows without their bytes: the PDF chip on an
upload message is broken after a resume, and the Sources side panels (`cl.Text`, whose
content is only kept through the storage client) come back empty. Documents themselves
already persist in Postgres and are not affected.

Add a local-disk storage client and a route that serves its files. See the Attachment
term in `CONTEXT.md` and the Persistence section of `docs/pdf-chat-decisions.md`. Spec:
`.scratch/attachments/spec.md`.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] A named volume `attachments` in `compose.yaml`, mounted into the app (for example at
  `/data/attachments`), owned by the app user. `make reset` already wipes it (`down --volumes`).
- [ ] A `BaseStorageClient` subclass that writes, reads and deletes files under that
  directory by object key (`threads/<thread id>/files/<element id>`). Keys that resolve
  outside the directory are rejected.
- [ ] A `@cl.data_layer` that returns `ChainlitDataLayer(DATABASE_URL, storage_client=...)`,
  replacing the automatic data layer that `DATABASE_URL` turns on.
- [ ] `get_read_url` returns the URL of a route mounted on Chainlit's FastAPI app. The
  route requires a logged-in user (no per-Thread ownership check: one demo account),
  returns 404 for missing or out-of-directory keys, and serves the stored mime type
  with `Content-Disposition: inline` for `application/pdf` and `attachment` otherwise.
- [ ] Deleting a Thread deletes its files from the volume (Chainlit calls `delete_file`;
  verify it, and fix it if not).
- [ ] Upload size limits are out of scope (`max_size_mb` stays; README follow-up).
- [ ] Threads created before this change keep broken chips and empty Sources; no backfill.
- [ ] Tests at one seam, the Attachment store from the outside: upload through the
  storage client against `tmp_path`, then fetch the `get_read_url` URL with Starlette's
  `TestClient` (bytes and mime type, inline vs attachment, delete then 404, unknown key 404,
  traversal key refused, logged out 401).
- [ ] Manual check: upload a PDF and ask a question, `make down && make run`, resume the
  Thread: the chip opens the PDF in the browser, and the Sources panels show their
  Document, Pages, quote and any ⚠️ warning. Rejected and duplicate uploads keep their chip.
- [ ] Docs: README `make reset` row mentions Attachments and the note about older
  Threads. The decisions doc, the pdf-chat spec and the glossary are already updated.
