# Acadra MCP Server

Python (FastMCP + Starlette) backend for Acadra: owns academic sources, records, progress, and study plans; serves MCP tools/resources to Alexa+ over Streamable HTTP and REST endpoints to the web app, both calling the same services and PostgreSQL. Includes Groq-backed extraction, Gmail polling, and the task-list planning layer.

```text
app/mcp_server/
├── pyproject.toml                  # Python package and dependencies
├── uv.lock                         # Locked dependency versions
├── .python-version                 # Python version used by uv
├── .env.example                    # Optional setting names; no secrets
├── README.md                       # Run, connect, and configuration instructions
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
    ├── tests/
    │   └── test_mcp_server.py      # Integration tests for MCP tools and resources
    └── jobs/
        └── gmail_poll.py           # One-minute Gmail intake and background extraction
```