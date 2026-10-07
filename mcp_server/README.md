# Study planner MCP server

This is the MCP backend described in [`system/STRUCTURE.md`](../../system/STRUCTURE.md). Manual plain text and uploaded HTML/PDF files are versioned and, when Groq is configured, extracted into source-grounded academic items and change events. Gmail account configuration and a console polling worker are available; Gmail message import, the full inbox, and planning are still planned.

The same manual-text service is available through an MCP tool for Alexa+ and a local REST endpoint for the future web application.

The Python package is `src`, with the entry point at `src/server.py`. Use the command below from `app/mcp_server`; running `src/server.py` directly bypasses its package imports.

## Set up

From `app/mcp_server`:

```powershell
uv sync
```

`uv` creates `.venv` and `uv.lock`. The lockfile should be kept with the project; `.venv` is ignored.

## Initialize PostgreSQL

Set `DATABASE_URL` in your shell or in `app/mcp_server/.env`, then run the initializer from `app/mcp_server`:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/study_planner"
uv run db/init_db.py
```

The initializer connects to the existing `postgres` maintenance database to create `study_planner` when missing, then creates the tables declared in `src/db/schema.py` using SQLAlchemy metadata. The PostgreSQL user must have `CREATEDB` permission. Since this is a fresh database, run the initializer once to create `source_connections` with `allowed_senders`. `create_all` does not change existing tables if the schema evolves later.

## Gmail connection setup

Set `ACADRA_GMAIL_CLIENT_ID` and `ACADRA_GMAIL_CLIENT_SECRET` in `app/mcp_server/.env`. In Google Cloud Console, register `http://127.0.0.1:8001/api/connections/gmail/callback` as an authorized redirect URI for a Web application OAuth client. Set `ACADRA_GMAIL_REDIRECT_URI` to that exact URI if you use a different local API port. `ACADRA_WEB_URL` defaults to `http://localhost:3000` for returning to the web page after consent. Keep the API bound to loopback; it has no student authentication yet.

Open `http://localhost:3000/gmail` after starting the API and web app. Enter 1–50 exact sender addresses, save them, then select **Continue with Google**. `GET` and `PUT /api/connections/gmail` expose the saved configuration; `GET /api/connections/gmail/authorize` and `/callback` handle Google OAuth. The client ID and secret stay on the backend. The Google refresh token is placed in the operating system credential manager and only its reference is saved in `source_connections`. A working OS credential manager is required to finish OAuth.

The included Uvicorn entry points disable access logs so OAuth callback codes do not appear in request logs. If you run the ASGI app behind another server or proxy, disable or redact query-string logging on this callback there too.

The `gmail.readonly` Google permission covers the Gmail account; the exact sender list is an application processing rule, not a Google permission boundary.

### Print newly arrived Gmail messages

After connecting the account, run the database initializer again to create the new `gmail_poll_cursors` table, then start this worker in a separate terminal from `app/mcp_server`:

```powershell
.\.venv\Scripts\python.exe -m src.jobs.gmail_poll
```

`uv run gmail-poll` is equivalent when `uv` is available. It checks Gmail every 60 seconds while running. On its **first** check it records the current Gmail history position; it prints only messages that arrive afterward from the configured exact sender addresses. Output is one JSON line per matching message with `id`, `sender`, `subject`, and bounded plain-text `content`. HTML-only messages are converted to text; attachments are ignored. Add `--once` to perform one check and exit. The worker uses the already connected account's stored refresh token and existing OAuth client settings. It does not save email bodies, create source revisions, or call Groq.

The history cursor advances only after the complete check succeeds. A failed request is retried on the next minute; a process interruption between printing and cursor storage can print the same message again. If Gmail reports that its history cursor has expired, the worker stops with an error rather than skip messages; full-rescan recovery is a later connector step. Run only one worker instance per connected account. The printed content is private, so use a local terminal and avoid capturing its output in shared logs.

## Manual text intake

Set `DATABASE_URL` in the server process environment before starting the server. Set `GROQ_API_KEY` to enable extraction; `GROQ_MODEL` defaults to `openai/gpt-oss-120b`. Groq receives the cleaned source text for extraction. The MCP tool `study_add_manual_text` accepts:

- `text` (required): plain text up to 64 KiB encoded as UTF-8.
- `title` (optional): a display title, up to 200 characters.
- `source_document_id` (optional): an ID previously returned by the tool to replace that manual source. Omit it to create a separate source, even if the text matches another paste.

The result contains `source_document_id`, `source_revision_id`, `revision_no`, `created_revision`, `processing_status`, `academic_item_ids`, and `review_count`. Replacing a source with equivalent normalized text updates its last-seen time but returns the existing revision with `created_revision: false`. Changed text creates the next revision. Processing can be `processed`, `already_processed`, `pending_configuration`, `failed`, or `superseded`. A source remains saved if extraction fails; re-submit the same text with its source ID to retry. Accepted academic fields are stored in `academic_items`, and created or edited values are recorded in `academic_item_changes`.

### REST endpoint for the web app

Run the combined REST and MCP listener from `app/mcp_server`:

```powershell
.\.venv\Scripts\python.exe -m src.api.app
```

After syncing the project, `uv run api-server` is equivalent. It binds to `127.0.0.1:8001` by default and serves REST at `/api` and MCP at `/mcp`. Pass `--port 8002` if that port is occupied. On startup, this app reads `app/mcp_server/.env`; an explicitly set `DATABASE_URL` takes precedence. An example request:

```powershell
$payload = @{ text = "Database assignment due Friday"; title = "Course note" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8001/api/sources/text -Method Post -ContentType application/json -Body $payload
```

`POST /api/sources/text` returns `201 Created` for a new source and `200 OK` for a replacement. Include the returned `source_document_id` in a later request to replace that source; omit it to create a new one. Invalid input returns `400`, `413`, `415`, or `422` as appropriate; an unknown source ID returns `404`; unavailable storage returns `503`. The listener has no student authentication yet and must remain on loopback. A future frontend can proxy `/api` to this port.

### Upload HTML or PDF files

`POST /api/sources/files` accepts multipart form fields `file` (required), `title` (optional), and `source_document_id` (optional, for replacing an existing source of the same file type). It returns the same revision and processing fields as text intake. UTF-8 `.html` and `.htm` files may be up to 256 KiB. Text-bearing `.pdf` files may be up to 5 MiB and 20 pages. Extracted text is capped at 64 KiB. Image-only/scanned PDFs need OCR and are rejected; password-protected PDFs are also rejected. The parser does not fetch HTML resources or execute embedded content.

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8001/api/sources/files -Method Post -Form @{ file = Get-Item 'C:\path\to\assignment.pdf'; title = 'Assignment handout' }
```

Original uploaded bytes are stored under `app/mcp_server/data/uploads/` (ignored by Git), with a hash and relative path in `source_files`. Uploaded revisions keep extracted `clean_text` for academic evidence and leave `raw_content` empty. Run the database initializer before the first upload.

### Retrieve academic items

`GET /api/academic-items` reads saved academic records. Optional query parameters are `item_type` (`assignment`, `announcement`, `reading`, or `event`), `course_id` (UUID), `review_state` (`verified`, `uncertain`, or `conflicting`), `due_from` (inclusive), `due_before` (exclusive), `limit` (1–100, default 20), and `offset` (default 0). Date filters require an ISO 8601 date-time with a time zone. Results are ordered by due date with undated items last. The response contains `items`, `has_more`, and `next_offset` for paging.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/academic-items?item_type=assignment&review_state=verified&limit=20' -Method Get
```

This endpoint reads accepted items stored in `academic_items`, including those from manual text and file extraction. `GET /api/academic-items/{item_id}/evidence` shows the source excerpts, date wording, and review reasons behind an extracted item. `GET /api/sources/{source_document_id}/candidates` shows the latest revision's candidates that need review and were not published as items; the older `/api/sources/text/{source_document_id}/candidates` path also works. An ambiguous or date-only deadline stays `null` in `due_at` and is retained in the evidence response for review. The mistaken direct-item `POST /api/academic-items` route has been removed.

Run the project-level checks from the repository root as shown in [`test/README.md`](../../test/README.md). Set `TEST_DATABASE_URL` to an initialized PostgreSQL database to also run revision and academic-persistence tests.

## Run locally

Start the MCP server over stdio:

```powershell
uv run mcp-server --transport stdio
```

An MCP client should launch that command as a subprocess. A quiet terminal is normal: stdio is reserved for MCP protocol messages.

For a local Streamable HTTP listener:

```powershell
uv run mcp-server --transport streamable-http
```

It listens on `127.0.0.1:8000` at `/mcp` by default. Set `STUDY_MCP_HOST` and `STUDY_MCP_PORT` in the shell if needed. `STUDY_MCP_TRANSPORT` selects the default transport. `.env.example` lists the optional settings; the standalone `mcp-server` entry point does not load `.env` automatically.

The HTTP listener is for local development only. Before remote exposure, add the student authentication and source authorization described in `STRUCTURE.md` and confirm Alexa+ transport requirements.
