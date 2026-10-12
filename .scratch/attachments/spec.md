# Spec: Attachments that survive restarts and resumed Threads

**Status:** ready-for-agent

## Problem Statement

When I come back to a Thread, after the app restarts or after I switch to another Thread
in the sidebar and back, the Thread doesn't look the way I left it. I can still ask
about its Documents, but the PDF I attached on my upload message is a broken chip I
can't open, and the Sources panels under earlier answers are empty, so I can no longer
see which quote backed which Citation. The history I'm resuming is only half there.

## Solution

Every Attachment is kept as it was sent, alongside its message, and comes back when the
Thread is resumed. Clicking the PDF chip on an old upload message opens the PDF in the
browser. The Sources panels of earlier answers show their Document, Pages and quote as
they did when the answer was written. This holds across `make down` / `make run`, and
`make reset` still wipes everything, Attachments included. Deleting a Thread deletes its
Attachments. Opening an Attachment requires being logged in.

## User Stories

1. As a user, I want the PDF chip on my upload message to still be there when I resume a Thread, so that I can see which PDFs I gave it.
2. As a user, I want clicking that chip to open the PDF in my browser, so that I can look at the original while I read an answer.
3. As a user, I want the PDF to open rather than download, so that I don't collect copies in my downloads folder.
4. As a user, I want the Sources panels of earlier answers to show their Document, Pages and quote after a resume, so that I can still check where an answer came from.
5. As a user, I want the ⚠️ warning from the Quote check to still show in a resumed Sources panel, so that I know which earlier quote couldn't be verified.
6. As a user, I want all of this to survive an app restart, so that a restart doesn't cost me my history.
7. As a user, I want all of this to survive switching to another Thread and back, so that I can work in several Threads at once.
8. As a user, I want Attachments that were rejected (no Text layer) to still show on their message, so that the history matches what I actually did.
9. As a user, I want Attachments skipped as duplicates to still show on their message, so that the history matches what I actually did.
10. As a user, I want deleting a Thread to delete its Attachments, so that nothing I uploaded lingers after I remove the Thread.
11. As a user, I want asking questions about a resumed Thread's Documents to keep working exactly as now, so that this change doesn't affect answers.
12. As a user, I want an Attachment's link to work only while I'm logged in, so that someone without the demo login can't fetch my PDFs.
13. As a user, I want a missing or bogus Attachment link to give a plain "not found", so that a broken link fails cleanly.
14. As a developer, I want `make down` to keep Attachments, so that stopping the stack behaves like it does for chats and Documents.
15. As a developer, I want `make reset` to delete Attachments together with chats and Documents, so that a reset really starts from empty.
16. As a developer, I want Attachments on a named Docker volume, so that rebuilding the image doesn't lose them.
17. As a developer, I want files on the volume owned by the app user, so that I can inspect them without fighting permissions.
18. As a developer, I want no extra container (no MinIO), so that the stack stays as simple to run as it is now.
19. As a developer, I want a storage key that tries to escape the Attachments directory to be refused, so that no request can read or write outside it.
20. As a developer, I want the README to say that Threads from before this change show no Attachments, so that nobody files that as a bug.
21. As a reviewer, I want the decisions doc to say why local disk was chosen over MinIO and Postgres, so that I can follow the trade-off.

## Implementation Decisions

- **An Attachment store module**, new. It has two public parts:
  - a **storage client** implementing Chainlit's `BaseStorageClient` (upload, delete,
    read URL, close) that keeps each file under a root directory by Chainlit's object
    key (`threads/<thread id>/files/<element id>`), together with its mime type so it
    can be served back with it;
  - a **serving route** on Chainlit's FastAPI app that returns a file by object key.
    `get_read_url` returns this route's URL for the key.
- **Every key is resolved against the root directory, and one that ends up outside it is
  refused**: upload raises, and the route answers 404. A missing key also answers 404.
- **The route requires a logged-in user**, through Chainlit's current-user dependency,
  and answers 401 otherwise. There is no per-Thread ownership check, since there is one
  demo account.
- **Disposition:** `inline` for `application/pdf`, `attachment` for anything else,
  regardless of the disposition Chainlit passes on upload.
- **The data layer is declared explicitly** (`@cl.data_layer`), returning Chainlit's own
  data layer on the existing `DATABASE_URL` with the storage client passed in. Setting
  `DATABASE_URL` no longer switches it on implicitly. Chat history storage is otherwise
  unchanged.
- **Deleting a Thread** relies on Chainlit's data layer calling the storage client's
  delete for each of the Thread's elements. The Attachment store only has to delete the
  file it is asked to.
- **Compose gets a named volume `attachments`**, mounted into the app and owned by the app
  user. Its mount path comes from a setting with a sensible default. `make reset`
  already removes all volumes.
- **Documents are untouched.** The documents and chunks tables, ingestion and retrieval
  don't change. A Document has no link to its Attachment.
- **The domain term is Attachment** (see the glossary), distinct from Document.
- **Docs:** the decisions doc and the original pdf-chat spec are already updated. The
  README's `make reset` row should mention Attachments, plus the note about older
  Threads.

## Testing Decisions

- **One seam: the Attachment store from the outside.** A test does what Chainlit and the
  browser do: upload through the storage client, then fetch the URL from `get_read_url`
  with Starlette's `TestClient` against an app that mounts the route. A good test checks
  what a caller sees (status, body bytes, content type, disposition), not how files are
  laid out on disk.
- **Cases:**
  - upload then fetch returns 200 with the same bytes and mime type
  - `inline` for a PDF, `attachment` for another type
  - delete then fetch returns 404
  - an unknown key returns 404
  - a traversal key is refused on upload and returns 404 on fetch
  - logged out returns 401, by overriding the current-user dependency
- **The root directory is `tmp_path`.** These are plain unit tests with no database or
  network, run by `make test`.
- **Prior art:** the unit tests that drive the Chat module through its public interface
  with in-memory fakes, and the async test style used throughout (`asyncio_mode = auto`).
- **Not covered by automated tests:** the explicit data-layer wiring and the Compose
  volume. Checking them would mean booting Chainlit against Postgres, which no test does
  today. The manual check is: upload a PDF and ask a question, `make down && make run`,
  resume the Thread, then confirm the chip opens the PDF inline and the Sources panels
  show their quotes. Then delete the Thread and confirm its files are gone from the
  volume.

## Out of Scope

- Backfilling Threads created before this change. Their bytes were never stored.
- Upload size limits. `max_size_mb` stays as it is, and limits remain a README follow-up.
- Per-Thread or per-user access checks on the route.
- Linking a Document to its Attachment, for example to open the PDF at a cited Page or
  to send Pages to Claude's native PDF input.
- Removing a single Attachment or Document from a Thread.
- Cloud object storage (S3, GCS, Azure) or MinIO.

## Further Notes

- Chainlit's data layer saves an `Element` row with no bytes and no content when no
  storage client is configured, and its insert has no column for a text element's
  content. That's why the Sources panels come back empty today, not just the PDF chips.
- Implementation issue: `.scratch/attachments/issues/01-persist-attachments.md`.
