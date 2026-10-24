# Acadra MCP Server

Python (FastMCP + Starlette) backend for Acadra: owns academic sources, records, progress, and study plans; serves MCP tools/resources to Alexa+ over Streamable HTTP and REST endpoints to the web app, both calling the same services and PostgreSQL. Includes Groq-backed extraction, Gmail polling, and the task-list planning layer.

```text
app/mcp_server/
├── pyproject.toml                  # Python package, dependencies, Vercel entrypoint
├── uv.lock                         # Locked dependency versions
├── .python-version                 # Python version used by uv and Vercel
├── vercel.json                     # Function duration for the single ASGI app
├── .vercelignore                   # Excludes local venv, cache, env, and tests
├── .env.example                    # Optional setting names; no secrets
├── README.md                       # Run, connect, deploy, and configuration instructions
├── data/uploads/                   # Runtime-only original uploads, ignored by Git
├── db/
│   ├── init_db.py                 # Create database and SQLAlchemy-declared tables
│   ├── migrate_gmail_ingestion.py # Add Gmail retry receipts and uniqueness indexes
│   └── migrate_planning_schema.py # Replace canvas-era planning tables with the task-list schema
└── src/
    ├── __init__.py
    ├── server.py                   # FastMCP instance and transport startup
    ├── dev.py                      # Run MCP and REST API servers together in one terminal
    ├── config.py                   # Typed settings and startup validation
    ├── errors.py                   # Error codes, mapping, and the tool error decorator
    ├── api/
    │   ├── app.py                  # Combined REST/MCP ASGI app; loads local .env
    │   ├── openapi.py              # OpenAPI description for REST routes
    │   ├── requests.py             # Bounded JSON body, validation, and path-ID helpers
    │   ├── schemas.py              # REST request and response contracts
    │   └── routes/
    │       ├── manual_text.py      # Text and multipart file source routes
    │       ├── gmail.py            # Gmail settings and Google OAuth callbacks
    │       ├── academic_items.py   # Academic item list, read, create, update, delete, and evidence
    │       ├── courses.py          # Course list, read, create, update, and delete
    │       ├── changes.py          # Academic item change feed
    │       ├── tasks.py            # Task create, read, update, reorder, delete, and plan views
    │       └── preferences.py      # Planning preferences read and write
    ├── mcp/
    │   ├── tools/
    │   │   ├── manual_text.py      # study_add_manual_text
    │   │   ├── academic_items.py   # Item and evidence reads; study_review_academic_item
    │   │   ├── changes.py          # study_get_changes_since
    │   │   ├── sources.py          # Source, revision, and candidate reads
    │   │   ├── courses.py          # Course and course-item reads
    │   │   ├── tasks.py            # Task CRUD, day moves, and plan views
    │   │   ├── preferences.py      # Planning defaults get/set
    │   │   └── connections.py      # Gmail operator reads and allowlist write
    │   ├── resources/
    │   │   └── academic_context.py # study:// read-only resource templates
    │   ├── schemas.py              # Pydantic enums and bounded input contracts
    │   ├── time_parsing.py         # Lenient date-only/date-time parsing for tool filters
    │   └── responses.py            # Pagination envelope and response formatting
    ├── auth/
    │   └── credential_store.py    # OS credential manager for Gmail refresh tokens
    ├── connectors/
    │   ├── gmail.py                # Sender validation, OAuth, and Gmail read requests
    │   ├── classroom.py            # Placeholder for Classroom client
    │   └── manual.py               # Bounded plain-text and file intake
    ├── ingestion/
    │   ├── text.py                 # Normalize extracted text
    │   ├── email_text.py           # Bounded Gmail MIME-to-text console preview
    │   ├── gmail_source.py         # Strict Gmail envelope, MIME limits, and quote removal
    │   ├── file_text.py            # HTML parsing and bounded PDF worker invocation
    │   ├── pdf_worker.py           # Isolated pypdf text extraction
    │   ├── chunking.py             # Structure-aware source windows for bounded extraction
    │   └── extraction.py           # Restricted chunk/map/merge/validate Groq extraction
    ├── domain/                     # Academic, source, progress, and plan models
    ├── services/
    │   ├── manual_text.py          # Source revision and original-file storage
    │   ├── gmail_connection.py     # Gmail connection and allowlist persistence
    │   ├── gmail_poll_state.py     # Persist Gmail history cursor
    │   ├── gmail_ingestion.py      # Save email revisions and retry queued extraction
    │   ├── source_processing.py    # Publish extracted facts and changes atomically
    │   ├── academic_items.py       # List/read items, evidence, and student corrections
    │   ├── changes.py              # Change feed with joined item context
    │   ├── sources.py              # Source documents, revisions, and summaries
    │   ├── courses.py              # Courses and their academic items
    │   ├── tasks.py                # Task CRUD lifecycle, link changes, ordering, and plan views
    │   └── preferences.py          # Single-scope planning preferences
    ├── db/
    │   ├── schema.py               # SQLAlchemy models for sources, items, and tasks
    │   └── session.py              # Async PostgreSQL engine and session scope
    └── jobs/
        └── gmail_poll.py           # One-minute Gmail intake and background extraction
tests/
└── test_mcp_server.py              # Integration tests for MCP tools and resources
```

`src` is imported as a package (for example, `src.server` and `src.mcp.tools`). Keeping the application `mcp/` folder inside `src` avoids a name conflict with the installed top-level `mcp` SDK.

## Run locally

From `app/mcp_server`:

```powershell
uv sync
uv run dev                          # MCP and REST listeners in one terminal
uv run mcp-server                   # combined REST + MCP app on 127.0.0.1:8000
uv run api-server                   # REST listener on 127.0.0.1:8001
uv run mcp-server --transport stdio # MCP only, over stdio
```

`uv run gmail-poll` starts the separate one-minute Gmail worker. See the Gmail section of the backend structure document for its cursor and retry behavior.

Copy `.env.example` to `.env` for local settings. The combined app loads `.env` at startup without overriding already-set process environment variables.

## Deploy on Vercel

The REST routes and the MCP transport are one Starlette application. `src/api/app.py` builds it with `mcp.streamable_http_app()` and appends the `/api/*` routes, so a single Vercel Function serves both and calls the same `src/services/` code and PostgreSQL database.

`pyproject.toml` tells Vercel which object to load:

```toml
[tool.vercel]
entrypoint = "src.api.app:app"
```

Vercel runs that ASGI object under Uvicorn and executes its Starlette lifespan, which starts the FastMCP session manager. The local `main()` functions in `src/api/app.py` and `src/server.py` are never used on Vercel.

1. Create a PostgreSQL database (for example Neon or Supabase) and apply the schema from `app/mcp_server` with the production URL:
   ```powershell
   $env:DATABASE_URL = "postgresql+asyncpg://..."
   uv run python -m db.init_db
   ```
   Use the provider's pooled connection URL, since serverless instances open short-lived connections.
2. Import the repository into Vercel and set **Root Directory** to `app/mcp_server`. The Python framework preset and `uv.lock` dependency install are detected automatically; no build command is needed.
3. Add the environment variables below for Production and Preview, then deploy.
4. Set the Google OAuth authorized redirect URI to `https://<deployment-host>/api/connections/gmail/callback` if Gmail is enabled.

Endpoints after deployment:

| Path | Purpose |
| --- | --- |
| `/mcp` | MCP Streamable HTTP endpoint for Alexa+ and other MCP clients |
| `/api/...` | REST surface for the web application |
| `/docs`, `/openapi.json` | Only when `STUDY_API_DEBUG` is enabled |

When `VERCEL` is present, `STUDY_MCP_STATELESS_HTTP` and `STUDY_MCP_JSON_RESPONSE` default to true. Stateless requests keep one MCP call independent of the function instance that served the previous one, and JSON responses avoid holding an SSE stream open. Set either variable to `False` to override; stateful sessions are only reliable on a single long-running process.

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | Yes | PostgreSQL URL; pooled serverless URL recommended |
| `GROQ_API_KEY` | For extraction | Without it, sources save as `pending_configuration` |
| `MODEL_PROVIDER`, `MODEL_NAME` | No | Groq defaults are in `.env.example` |
| `STUDY_MCP_STATELESS_HTTP` | No | Defaults to true on Vercel |
| `STUDY_MCP_JSON_RESPONSE` | No | Defaults to true on Vercel |
| `STUDY_MCP_ALLOWED_HOSTS` | No | Comma-separated exact Host allowlist for `/mcp`; otherwise Host validation is disabled behind Vercel |
| `STUDY_MCP_ALLOWED_ORIGINS` | No | Comma-separated exact Origin allowlist for `/mcp` |
| `STUDY_MCP_DEBUG` | No | Keep false in production; true renders debug tracebacks |
| `STUDY_UPLOAD_ROOT` | No | Defaults to `/tmp/acadra/uploads` on Vercel |
| `ACADRA_GMAIL_CLIENT_ID`, `ACADRA_GMAIL_CLIENT_SECRET`, `ACADRA_GMAIL_REDIRECT_URI` | Only for Gmail | Redirect URI must be the deployed callback |
| `ACADRA_WEB_URL` | No | Frontend origin used by the Gmail authorization redirect |

Smoke-test the MCP endpoint after the first deploy:

```powershell
curl.exe -i "https://<deployment-host>/mcp" `
  -H "content-type: application/json" `
  -H "accept: application/json, text/event-stream" `
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
```

### Serverless limitations

- **Gmail credentials:** `src/auth/credential_store.py` uses the operating system keyring, which Vercel Functions do not provide. The Gmail OAuth callback cannot persist a refresh token there. Keep Gmail setup local, or add a secret-manager or database-backed credential store before enabling it in production.
- **Gmail polling:** `gmail-poll` is a long-running loop, not a request handler. Run it on a worker host, or convert one poll pass into an authenticated route scheduled by Vercel Cron.
- **Uploaded files:** the project filesystem is read-only. Originals are written to `/tmp/acadra/uploads` and disappear when the instance is recycled; extracted text, revisions, and metadata remain in PostgreSQL. Use object storage for durable originals.
- **Body size:** Vercel caps request bodies at 4.5 MB, below the app's 5 MiB PDF limit. Larger files need direct-to-object-storage uploads.
- **Authorization:** the REST surface still has no student authentication or CORS configuration. Treat the deployment as private until an authorization boundary exists.