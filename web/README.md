# Manual source entry

This Next.js app provides a basic page for entering a study source as pasted text or an HTML/PDF file at `http://localhost:3000/`, plus Gmail connection setup at `http://localhost:3000/gmail`.

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

The web routes `/api/manual-entry` and `/api/gmail-connection` forward requests to the backend at `http://127.0.0.1:8001` by default. To use another API address, copy `.env.example` to `.env.local` and set `MANUAL_SOURCE_API_URL` to the backend base URL. This is read only on the Next.js server. Before using `/gmail`, configure Google OAuth and rerun the backend database initializer as described in the backend README.

Text is limited to 64 KiB. HTML files are limited to 256 KiB; PDFs are limited to 5 MiB and 20 pages. The backend validates and stores the source and extracts academic items when configured. Scanned PDFs need OCR and are currently unsupported.
