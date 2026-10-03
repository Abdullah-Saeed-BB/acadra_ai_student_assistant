# Study planner MCP server

This is the MCP backend described in [`system/STRUCTURE.md`](../../system/STRUCTURE.md). Its first data-processing slice accepts manually pasted plain text and stores source revisions. Academic extraction, inbox items, file/HTML intake, and external connectors are still planned.

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
uv run db/db_init.py
```

The initializer connects to the existing `postgres` maintenance database to create `study_planner` when missing, then creates the tables declared in `src/db/schema.py`. The PostgreSQL user must have `CREATEDB` permission. This initializer does not update existing tables when the model changes.

## Manual text intake

Set `DATABASE_URL` in the server process environment before starting the server. The MCP tool `study_add_manual_text` accepts:

- `text` (required): plain text up to 64 KiB encoded as UTF-8.
- `title` (optional): a display title, up to 200 characters.
- `source_document_id` (optional): an ID previously returned by the tool to replace that manual source. Omit it to create a separate source, even if the text matches another paste.

The result contains `source_document_id`, `source_revision_id`, `revision_no`, and `created_revision`. Replacing a source with equivalent normalized text updates its last-seen time but returns the existing revision with `created_revision: false`. Changed text creates the next revision. This tool stores source material only; it does not yet extract assignments or create inbox changes.

Run the project-level checks from the repository root as shown in [`test/README.md`](../../test/README.md). Set `TEST_DATABASE_URL` to an initialized PostgreSQL database to also run the revision test; that test rolls its transaction back.

## Run locally

Start the server over stdio (the default):

```powershell
uv run mcp-server
```

An MCP client should launch that command as a subprocess. A quiet terminal is normal: stdio is reserved for MCP protocol messages.

For a local Streamable HTTP listener:

```powershell
uv run mcp-server --transport streamable-http
```

It listens on `127.0.0.1:8000` at `/mcp` by default. Set `STUDY_MCP_HOST` and `STUDY_MCP_PORT` in the shell if needed. `STUDY_MCP_TRANSPORT` can also select the default transport. `.env.example` lists the optional settings; `.env` is not loaded automatically.

The HTTP listener is for local development only. Before remote exposure, add the student authentication and source authorization described in `STRUCTURE.md` and confirm Alexa+ transport requirements.
