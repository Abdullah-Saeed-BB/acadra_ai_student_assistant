# Acadra

An AI-powered academic assistant integrated with Alexa+ that consolidates university information from multiple sources, tracks assignments and announcements, and transforms deadlines into personalized, actionable study plans.

Students can use natural conversations to monitor progress, identify priorities, and dynamically manage their academic schedules. The web workspace mirrors the same data: a Today plan, upcoming days, backlog, inbox of changes, courses and academic items, manual source entry (pasted text or HTML/PDF files), Gmail connector setup, and an Alexa+ simulator.

## Description

Acadra brings together academic information scattered across email, course materials, and manual notes into one shared study-planner backend:

- **Ingestion** — manual plain text, uploaded UTF-8 HTML/PDF files, and Gmail messages from an exact sender allowlist are versioned as source revisions.
- **Extraction** — a restricted LLM graph (Groq by default) turns source text into source-grounded academic items (assignments, announcements, readings, events) with evidence, review states, and change events.
- **Planning** — tasks, one-level steps, selected days, and planning preferences power Today / Upcoming / Backlog views and drag reordering.
- **Interfaces** — Alexa+ uses MCP tools/resources; the student web app uses REST endpoints that call the same services and database.

## Technologies
### Frontend
![Next.js](https://img.shields.io/badge/Next.js_16-080808?style=for-the-badge&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)
![Zod](https://img.shields.io/badge/Zod-3E67B1?style=for-the-badge&logo=zod&logoColor=white)

### Backend
![Python](https://img.shields.io/badge/Python_3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastMCP](https://img.shields.io/badge/FastMCP-000000?style=for-the-badge)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![uv](https://img.shields.io/badge/uv-7928CA?style=for-the-badge&logo=astral&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Starlette](https://img.shields.io/badge/Starlette-F75A0D?style=for-the-badge&logo=starlette&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-2CA5E0?style=for-the-badge&logo=uvicorn&logoColor=white)

### AI Models & Orchestration
![LangChain](https://img.shields.io/badge/LangChain-1E3C3B?style=for-the-badge&logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-000000?style=for-the-badge&logo=langgraph&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-GPT_OSS_120b-F55036?style=for-the-badge&logo=groq&logoColor=white)
![DeepSeek](https://img.shields.io/badge/OpenRouter-Deepseek_V4_Flash_0731-0066FF?style=for-the-badge&logo=openrouter&logoColor=white)

## Installing

### Requirements
- **Python 3.12+** and **uv** (https://docs.astral.sh/uv/)
- **Node.js 20+** and **npm**
- **PostgreSQL** (a running instance and a user with `CREATEDB`)
- (Optional) **Groq API key** for extraction and the Alexa+ bridge
- (Optional) **Google OAuth credentials** for the Gmail connector

### Step-by-step

1. **Clone and enter the project**
   ```powershell
   cd C:\Projects\acadra
   ```

2. **Set up the backend**
   ```powershell
   cd app\mcp_server
   uv sync
   Copy-Item .env.example .env
   ```
   Edit `app/mcp_server/.env` and set at least `DATABASE_URL` and `GROQ_API_KEY`. For Gmail, also set `ACADRA_GMAIL_CLIENT_ID`, `ACADRA_GMAIL_CLIENT_SECRET`, and `ACADRA_GMAIL_REDIRECT_URI`.

3. **Initialize PostgreSQL**
   ```powershell
   $env:DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/study_planner"
   uv run db/init_db.py
   ```
   For databases created before the task-list schema, also run:
   ```powershell
   .\.venv\Scripts\python.exe -m db.migrate_planning_schema
   .\.venv\Scripts\python.exe -m db.migrate_gmail_ingestion
   ```

4. **Start the backend** (combined REST + MCP listener)
   ```powershell
   .\.venv\Scripts\python.exe -m src.api.app
   # or: uv run api-server
   ```
   It binds to `http://127.0.0.1:8001` and serves REST at `/api` and MCP at `/mcp`.

5. **(Optional) Start the Gmail poll worker** in a separate terminal
   ```powershell
   .\.venv\Scripts\python.exe -m src.jobs.gmail_poll
   # or: uv run gmail-poll
   ```

6. **Set up the frontend**
   ```powershell
   cd ..\web
   npm install
   Copy-Item .env.example .env.local
   ```
   Adjust `MANUAL_SOURCE_API_URL` / `MCP_SERVER_URL` in `.env.local` if needed, then:
   ```powershell
   npm run dev
   ```

7. **Open the app** at `http://localhost:3000`. The Today view is the landing page; manual source entry is at `/sources/new`, connectors at `/connecters`, and the Alexa+ simulator at `/alexa+_simulator`.

### Notes
- The backend has no student authentication yet; keep it on loopback and do not expose it publicly.
- Scanned/image-only and encrypted PDFs are not supported (OCR required).
- Run backend tests from `app/mcp_server` with `uv run python -m unittest tests.test_mcp_server`.
