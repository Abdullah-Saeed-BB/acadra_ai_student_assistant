# Study planner MCP server

This is the runnable MCP server scaffold described in [`system/STRUCTURE.md`](../../system/STRUCTURE.md). It intentionally has no academic tools, resources, connectors, or storage behavior yet.

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

The initializer connects to the existing `postgres` maintenance database to create `study_planner` when missing, then creates the tables declared in `src/db/schema.py`. The PostgreSQL user must have `CREATEDB` permission. The temporary `Student` model creates a `students` table; this initializer does not update existing tables when the model changes.

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
