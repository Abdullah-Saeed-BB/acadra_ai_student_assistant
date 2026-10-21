<h1 align="center">Acadra</h1>

An AI-powered academic assistant integrated with Alexa+ that consolidates university information from multiple sources, tracks assignments and announcements, and transforms deadlines into personalized, actionable study plans.

Students can use natural conversations to monitor progress, identify priorities, and dynamically manage their academic schedules. The web workspace mirrors the same data: a Today plan, upcoming days, backlog, inbox of changes, courses and academic items, manual source entry (pasted text or HTML/PDF files), Gmail connector setup, and an Alexa+ simulator.

## Description

Acadra brings together academic information scattered across email, course materials, and manual notes into one shared study-planner backend:

- **Ingestion** — manual plain text, uploaded UTF-8 HTML/PDF files, and Gmail messages from an exact sender allowlist are versioned as source revisions.
- **Extraction** — a restricted LLM graph (Groq by default) turns source text into source-grounded academic items (assignments, announcements, readings, events) with evidence, review states, and change events.
- **Planning** — tasks, one-level steps, selected days, and planning preferences power Today / Upcoming / Backlog views and drag reordering.
- **Interfaces** — Alexa+ uses MCP tools/resources; the student web app uses REST endpoints that call the same services and database.

## Technologies

# Technologies



| Frontend | Backend | AI Models & Orchestration |
| --- | --- | --- |
| ![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)<br>![Next.js](https://img.shields.io/badge/Next.js_16-080808?style=for-the-badge&logo=next.js&logoColor=white) ![Zod](https://img.shields.io/badge/Zod-3E67B1?style=for-the-badge&logo=zod&logoColor=white) | ![Python](https://img.shields.io/badge/Python_3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white) ![FastMCP](https://img.shields.io/badge/FastMCP-000000?style=for-the-badge) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white) ![uv](https://img.shields.io/badge/uv-7928CA?style=for-the-badge&logo=astral&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white) ![Starlette](https://img.shields.io/badge/Starlette-F75A0D?style=for-the-badge&logo=starlette&logoColor=white) ![Uvicorn](https://img.shields.io/badge/Uvicorn-2CA5E0?style=for-the-badge&logo=uvicorn&logoColor=white) | ![LangGraph](https://img.shields.io/badge/LangGraph-000000?style=for-the-badge&logo=langgraph&logoColor=white)<br>![LangChain](https://img.shields.io/badge/LangChain-1E3C3B?style=for-the-badge&logo=langchain&logoColor=white) ![Groq](https://img.shields.io/badge/Groq-GPT_OSS_120b-F55036?style=for-the-badge&logo=groq&logoColor=white) ![DeepSeek](https://img.shields.io/badge/OpenRouter-Deepseek_V4_Flash_0731-0066FF?style=for-the-badge&logo=openrouter&logoColor=white) |

## Installing

### Requirements
- **Python 3.12+** and **uv** (https://docs.astral.sh/uv/)
- **Node.js 20+** and **npm**
- **PostgreSQL** (a running instance and a user with `CREATEDB`)
- **Groq API key** _(Or any AI provider you prefer)_ for extraction and the Alexa+ bridge 
- (Optional) **Google OAuth credentials** for the Gmail connector

### Step-by-step

1. **Clone project**
   ```git
   git clone https://github.com/Abdullah-Saeed-BB/acadra_ai_student_assistant.git
   ```

2. **Enter the project**
   ```powershell
   cd acadra_ai_student_assistant
   ```

3. **Set up the backend**
   ```powershell
   cd mcp_server
   uv sync
   Copy-Item .env.example .env
   ```
   Edit `mcp_server/.env` and set at least `DATABASE_URL` and `GROQ_API_KEY`. For Gmail polling, also set `ACADRA_GMAIL_CLIENT_ID`, `ACADRA_GMAIL_CLIENT_SECRET`, and `ACADRA_GMAIL_REDIRECT_URI`. (Get them from the [Google Cloud Console](https://console.cloud.google.com/))

4. **Initialize Database on PostgreSQL**
   ```powershell
   uv run db/init_db.py
   ```

5. **Start the backend** (combined REST + MCP listener)
   ```powershell
   uv run dev
   ```
   It binds to `http://127.0.0.1:8001` to serves REST, and to `http://127.0.0.1:8000` to serves MCP.

6. **(Optional) Start the Gmail poll worker** in a separate terminal
   Enter to `/mcp_server` then run: 
   ```powershell
   uv run gmail-poll
   ```
   > Note: You must connect to Gmail in the connecters page after running the frontend to start polling your Gmail.


7. **Set up the frontend**
   Create new terminal to run the frontend
   ```powershell
   cd acadra_ai_student_assistant\web
   npm install
   Copy-Item .env.example .env
   ```
   Adjust `MANUAL_SOURCE_API_URL` / `MCP_SERVER_URL` in `.env.local` if needed, then:
   ```powershell
   npm run dev
   ```

8. **Open the app** at `http://localhost:3000`. The Today view is the landing page; manual source entry is at `/sources/new`, connectors at `/connecters`, and the Alexa+ simulator at `/alexa+_simulator`.

### Notes
- The backend has no student authentication yet; keep it on loopback and do not expose it publicly.
- Scanned/image-only and encrypted PDFs are not supported (OCR required).

## Screenshots

<img width="1901" height="979" alt="‏‏SCR (93)" src="https://github.com/user-attachments/assets/872c8557-fa60-4bfa-84f5-c494e83b84c6" />
<img width="1901" height="979" alt="‏‏SCR (92)" src="https://github.com/user-attachments/assets/ee6a938b-8000-419c-b2da-ec9b347917e4" />
<img width="1901" height="979" alt="‏‏SCR (94)" src="https://github.com/user-attachments/assets/c8ce8d85-7584-4d3f-aec1-d83e16045198" />
<img width="1901" height="979" alt="‏‏SCR (96)" src="https://github.com/user-attachments/assets/460df34f-24f5-4b9b-b5d4-0286396ad72d" />
<img width="1901" height="979" alt="‏‏SCR (95)" src="https://github.com/user-attachments/assets/8a0a10ca-c3f0-422d-afd0-f636481c4340" />
<img width="1901" height="979" alt="‏‏SCR (97)" src="https://github.com/user-attachments/assets/2cb0c7f5-8faa-4f30-bbe9-fe39eee6c6d2" />
<img width="1901" height="979" alt="‏‏SCR (100)" src="https://github.com/user-attachments/assets/7ebf9f21-0b61-4d48-92a3-8de3cf6655f5" />
