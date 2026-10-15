# Acadra study workspace

This Next.js app is the Acadra student workspace. `http://localhost:3000/` is the Today landing view inside a shared sidebar shell. Manual source entry (pasted text or an HTML/PDF file) lives at `http://localhost:3000/sources/new`, Gmail connection setup is at `http://localhost:3000/gmail`, and the Alexa+ simulator chat is at `http://localhost:3000/alexa+_simulator`. The remaining sidebar routes — Upcoming, Backlog, All tasks, Inbox, Courses, and Settings — render a branded placeholder until their views and backend routes are built.

The shell follows the design system in [DESIGN.md](DESIGN.md): warm Paper, dark Ink, restrained action teal, fine rules, and Fraunces used once per view. Manrope and Fraunces are self-hosted through `next/font`, which downloads them during `next build`; both fall back to Arial and Georgia if unavailable.

## Run locally

Start the Python API first from `app/mcp_server`:

```powershell
.\.venv\Scripts\python.exe -m src.api.app
```

The API requires an initialized PostgreSQL database and `DATABASE_URL`; see [the backend README](../mcp_server/README.md). Then start the web app from `app/web`:

```powershell
npm install
npm run dev
```

The web routes `/api/manual-entry` and `/api/gmail-connection` forward requests to the backend at `http://127.0.0.1:8001` by default. To use another API address, copy `.env.example` to `.env.local` and set `MANUAL_SOURCE_API_URL` to the backend base URL. This is read only on the Next.js server.

`/api/alexa-chat` is the Alexa+ bridge. It calls the Python MCP server's Streamable HTTP `/mcp` endpoint through `lib/mcp-client.ts` (server-side only) and returns `{ reply }`; the browser never reaches the MCP server. Set `MCP_SERVER_URL` to override the default `http://127.0.0.1:8001/mcp`. That default targets the combined REST + MCP app (`uv run api-server`, port 8001); the standalone `uv run mcp-server --transport streamable-http` serves `/mcp` on `STUDY_MCP_PORT` (default 8000) instead. When the bridge is unreachable the simulator answers with scripted replies.

Before using `/gmail`, configure Google OAuth and rerun the backend database initializer as described in the backend README.

Text is limited to 64 KiB. HTML files are limited to 256 KiB; PDFs are limited to 5 MiB and 20 pages. The backend validates and stores the source and extracts academic items when configured. Scanned PDFs need OCR and are currently unsupported.

## Design assets

`components/acadra-mark.tsx` draws the temporary waypoint mark and `acadra` lockup to match [DESIGN.md](DESIGN.md). Replace it with the outlined vectors from `Brand Assets/Acadra Mark.svg` and `Brand Assets/Acadra Logo.svg` once those files are copied into `public/`.
