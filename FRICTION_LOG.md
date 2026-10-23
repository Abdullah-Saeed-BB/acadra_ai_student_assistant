# Acadra Friction Log

**Date:** 2026-10-23  
**Project:** Acadra — AI academic assistant for university students  
**Workspace:** `C:\Projects\acadra`. The Git repository root is `app/`; after cloning, that root is the `acadra_ai_student_assistant/` folder containing `mcp_server/` and `web/`. In this wrapper workspace, the same folders appear as `app/mcp_server/` and `app/web/`.  
**Reference:** Project proposal at `system/PROJECT_PROPOSAL.md`  
**Prepared by:** Build session using OpenCode  
**Scope:** End-to-end build and demo review of Acadra against the product proposal. Manual review prompts were read-only; the backend integration tests were also run and may have refreshed test preferences, but no source or task data was intentionally changed by the review prompts.

This is a working friction log, not a bug bounty. It records the tasks attempted while running and reviewing Acadra, the gap between the proposal and the implementation, and the smallest changes that would remove the friction. Several entries are scope or documentation gaps rather than code defects; they are included because they affected the build/demo experience.

## Severity scale

| Severity | Meaning |
| --- | --- |
| Critical | Blocks the demo, loses data, or creates a security/privacy problem. |
| High | A core student job or core source is unreliable, misleading, or missing; no clean in-product workaround. |
| Medium | The core flow is possible, but requires a manual workaround or causes localized confusion. |
| Low | Polish, documentation, or developer-experience issue with no functional impact. |

## Investigation setup

| Item | Value |
| --- | --- |
| OS | Windows |
| Python | 3.12.5 |
| uv | 0.9.28 |
| Node | 24.18.0 |
| npm | 11.16.0 |
| Backend | FastMCP + Starlette + PostgreSQL |
| Frontend | Next.js 16.3.8 |
| Backend start | `uv run dev` (REST on 8001, MCP on 8000) |
| Frontend start | `npm run dev` (port 3000) |
| Database | Reachable; `SELECT 1` returned `1` |

The backend and frontend were started locally and exercised through their real HTTP surfaces. The Alexa+ bridge was called through `POST /api/alexa-chat`; the frontend was built and linted. Secrets from `.env` were not printed or included in this document.

## Summary

| ID | Task attempted | Area | Severity | Workaround |
| --- | --- | --- | --- | --- |
| F-01 | Follow the README to start both apps | Onboarding | Medium | Use `.env` and match the MCP port to the launch mode |
| F-02 | Connect Gmail and import recent course mail | Gmail connector | High | Run the worker and wait for new mail, or upload manually |
| F-03 | Turn a deadline into a plan and keep it current after a change | Planning | High | Ask Alexa to create/replan, or create tasks by hand |
| F-04 | Check that Today respects my daily study limit | Planning | High | Ask Alexa for an overload check; move tasks manually |
| F-05 | Ask what changed since I last checked | Inbox | Medium | Say “since yesterday” instead |
| F-06 | Turn a course page into clean assignment records | Extraction | High | Review and correct records manually |
| F-07 | Inspect the original source and its extracted candidates | Provenance | Medium | Call the candidates API directly |
| F-08 | Connect the MCP server to a real Alexa+ client | Integration | High | Use the local simulator only |
| F-09 | Pull Google Classroom data and plan around classes/work | Sources and availability | High | Upload sources manually and state constraints in chat |
| F-10 | Ask Alexa to remove a duplicate task | Voice editing | Medium | Delete it on the web page |
| F-11 | Open Connectors at the obvious URL and run lint | Frontend polish | Low | Use the sidebar link; warnings do not block |

---

## F-01 — Quick-start mixes `.env` and `.env.local`, and the MCP port depends on the launch mode

**Area:** Developer onboarding, environment configuration  
**Severity:** Medium

**Task attempted:** Follow `app/README.md` from a clean clone to start the backend and frontend, and connect the frontend to the MCP endpoint.

**Steps taken:**

1. Read `app/README.md` steps 1–8.
2. Confirmed the repository root locally is `C:\Projects\acadra\app` (`git rev-parse --show-toplevel`). After cloning, that root is the `acadra_ai_student_assistant/` folder and contains `mcp_server/` and `web/`. Therefore `cd mcp_server` from the clone root and `cd acadra_ai_student_assistant\web` from a fresh terminal in the parent directory are valid commands.
3. Compared step 7 with `app/web/.env.example` and the two backend entry points in `pyproject.toml`.
4. Started the backend with `uv run dev` and the frontend with `npm run dev`.

**Expected:** One environment file is created and edited, and the frontend’s `MCP_SERVER_URL` matches whichever backend command the README tells the reader to run. The backend serves REST on `127.0.0.1:8001` and MCP on `127.0.0.1:8000`; the frontend serves on `localhost:3000`.

**Actual:**

- Step 7 runs `Copy-Item .env.example .env`, then tells the reader to adjust `MANUAL_SOURCE_API_URL` and `MCP_SERVER_URL` in `.env.local`. The reader has an `.env`, not an `.env.local`. Next.js loads both, so this usually works, but the instruction disagrees with the command.
- Two documented backend modes exist: `uv run dev` starts MCP on 8000 and REST on 8001; `uv run api-server` serves a combined REST and MCP app on 8001. `app/web/.env.example` defaults `MCP_SERVER_URL` to `http://127.0.0.1:8000/mcp`. A reader who chooses `api-server` without changing the URL gets a bridge that cannot connect, which the simulator renders as a fallback error.

**Evidence:**

- `app/README.md`, steps 5–7.
- `app/mcp_server/src/dev.py`, `run_mcp()` and `run_api()`.
- `app/mcp_server/src/api/app.py`, `app = mcp.streamable_http_app()` and `uvicorn.run(..., port=args.port)`.
- `app/web/.env.example`, lines explaining the 8000/8001 port choice.

**Impact:** The backend can start successfully while the frontend talks to the wrong port, which looks like a broken product rather than a configuration choice. The environment-file mismatch sends the reader to a file that the previous command did not create.

**Workaround used:** Used `uv run dev`, kept the existing `.env` files, and pointed the frontend at `http://127.0.0.1:8000/mcp`. When using the combined `api-server` mode, the working value is `http://127.0.0.1:8001/mcp`.

**Actionable suggestion:**

- Update step 7 to say “edit `.env`” if that is the file being created, or change the copy command to create `.env.local`.
- Make one backend start command canonical in the README. If both `dev` and `api-server` stay supported, derive `MCP_SERVER_URL` from the same configuration or show both matching pairs explicitly.
- Add a startup log or health check that prints the MCP URL the frontend will use and verifies it before the simulator opens.
- Add a clean-checkout smoke test that follows the README literally and checks the REST port, MCP port, and frontend port.

---

## F-02 — Gmail import is implemented, but the UI says it is not; the first connection imports nothing

**Area:** Gmail connector, ingestion UI, documentation  
**Severity:** High

**Task attempted:** Verify that connecting Gmail imports recent course assignments and announcements into Acadra.

**Steps taken:**

1. Read the connector card at `/connecters` and the form at `/connecters/gmail`.
2. Traced the backend path in `app/mcp_server/src/jobs/gmail_poll.py`, `src/services/gmail_ingestion.py`, and `src/connectors/gmail.py`.
3. Checked what `poll_once` does on its first run, before any `historyId` cursor exists.
4. Compared the behavior with the Gmail bullet in the proposal and the worker instructions in the README.

**Expected:** Per the proposal, Gmail is a core source: “Email — Via Gmail.” Connecting the account and saving permitted senders should start importing recent academic mail, or at least make the import status and its limitations visible.

**Actual:**

- The connector card says: “Message import is not yet implemented.”
- The form says the setup “does not fetch messages yet” and that other senders “will be skipped when import is added.”
- A working worker exists: `uv run gmail-poll` imports future messages, stores durable retries, and advances a history cursor.
- On first run, `poll_once` records the current mailbox position and returns `0` (“Initialized at the current mailbox position; watching for new messages”). It does not backfill existing messages.
- After OAuth, the form says the sender list is “ready for the first import,” but nothing is imported until a new matching message arrives.

**Evidence:**

- `app/web/app/connecters/page.tsx`, connector description.
- `app/web/app/connecters/gmail/gmail-connection-form.tsx`, the “does not fetch messages yet” and “when import is added” copy.
- `app/mcp_server/src/jobs/gmail_poll.py`, `poll_once` baseline branch and the one-minute loop.
- `app/mcp_server/README.md` and `app/README.md`, Gmail worker instructions.

**Impact:** A new user connects Gmail, sees no data, and concludes the connector failed. The UI actively contradicts a working backend feature. For a demo, this is worse than a missing feature because it hides working functionality.

**Workaround used:** The available workaround is to run the worker and wait for new mail, or upload a source manually. For this review I used existing data and inspected the worker path; I did not complete a live Google OAuth connection.

**Actionable suggestion:**

- Replace the “not implemented” copy with the real state: “Import worker: running/not running,” “Last checked,” and “Messages imported.”
- Add an explicit initial lookback (for example, 7 or 30 days) with a page cap and a progress indicator, or add an “Import recent mail” button for the first connection.
- Show rejected/skipped senders and the last poll result in the connector page.
- Add an integration test that connects a seeded mailbox and verifies the first visible import, not only future-message ingestion.

---

## F-03 — Deadlines do not become plans automatically, and source changes do not refresh existing plans

**Area:** Planning pipeline, source processing, Gmail worker  
**Severity:** High

**Task attempted:** Trace what happens after an assignment is extracted with a deadline, then trace the same path after the deadline changes.

**Steps taken:**

1. Traced the extraction write path in `app/mcp_server/src/services/source_processing.py`.
2. Checked what happens after a Gmail message is accepted in `src/services/gmail_ingestion.py` and `src/jobs/gmail_poll.py`.
3. Searched the task service for any call triggered by an academic-item create or edit.
4. Compared the observed path with the proposal’s “From Data To Insights” and “Keep the plan current” claims.

**Expected:** Per the proposal:

- “Convert every deadline into a recommended start date, milestone plan, estimated work blocks, and reminders.”
- “New assignments, changed deadlines, moved classes, newly posted readings, and event announcements must update the plan automatically.”

**Actual:**

- Source processing creates or updates `AcademicItem` rows and writes `AcademicItemChange` events. It does not create or update `Task` rows.
- Gmail ingestion queues and processes revisions; the poll worker only drives ingestion and extraction.
- Existing tasks linked to an academic item are not recalculated when the item’s due date, weight, or details change.
- There is no stale-plan flag, reminder row, or generated milestone plan. A user must ask Alexa to plan the work or create tasks manually on the web.

**Evidence:**

- `app/mcp_server/src/services/source_processing.py`, item creation and change-event blocks.
- `app/mcp_server/src/jobs/gmail_poll.py`, the poll and processing loop.
- `app/mcp_server/src/services/tasks.py`, task CRUD and plan views; there is no source-processing import or change-listener path.
- `system/PROJECT_PROPOSAL.md`, “From Data To Insights” and “Keep the plan current.”

**Impact:** The biggest proposed transformation — deadline to an actionable plan — remains a manual conversation. If a professor moves a deadline, the Inbox may show the edit while Today keeps the old plan. Students can act on stale dates, which is exactly the trust problem the proposal is trying to solve.

**Workaround used:** The only product workaround is to create or adjust tasks manually, or ask Alexa to do it explicitly. I inspected both paths but did not mutate the demo data; no automatic plan refresh was available to test.

**Actionable suggestion:**

- Add a small planning service that converts an academic item into recommended work blocks and milestone tasks using due date, grade weight, remaining effort, lag, and preferences.
- Call it from source publishing when a new item is created, and from item updates when a field that affects planning changes.
- Keep completed steps; re-plan only unfinished work, and mark the plan “needs review” instead of silently moving work.
- Expose the action through `POST /api/plan/generate` and an MCP tool such as `study_plan_academic_item`, with a dry-run option.
- Add reminders as a separate table/worker if reminders remain in scope, or remove “reminders” from the MVP promise.

---

## F-04 — Today’s effort ignores the daily preference and double-counts nested steps

**Area:** Today/Upcoming plan views, preferences, Alexa answers  
**Severity:** High

**Task attempted:** Check that Today is a realistic plan that respects the saved daily workload preference and gives one consistent effort total.

**Steps taken:**

1. Read `GET /api/preferences` through the backend.
2. Read `GET /api/plan/today`.
3. Asked the Alexa simulator, “What is on my plan today? Keep it short.”
4. Asked, “What is most urgent right now? Do not change anything. Keep it short.”
5. Asked, “Will next week be a bad week for me? Do not change anything. Keep it short.”
6. Read `get_today_plan`, `get_upcoming_plan`, the Today page, and the task grouping component.

**Expected:** Per the proposal, the product should “surface a small intelligent ‘today’ plan, not dump the whole semester schedule,” and a realistic plan must account for available study time. A saved `preferred_daily_minutes` should either cap the plan, warn when the plan exceeds it, or clearly label the plan as over budget.

**Actual:**

- Preferences returned `preferred_daily_minutes: 150` and `focus_task_count: 4`.
- `/api/plan/today` returned `total_estimated_minutes: 345` for one 240-minute parent task plus its 60-minute and 45-minute steps.
- The Today page shows `345 min` without an over-limit warning.
- Alexa answered “about 5.75 hours total” in one turn and “about 4 hours of work left” in another for the same plan. The first figure equals the API’s 345-minute sum; the second equals the 240-minute parent estimate alone.
- `Upcoming` starts on today and includes today’s tasks, so the same work appears on both Today and Upcoming.
- The plan service sums every task, including child steps, and never reads `planning_preferences`.

**Evidence:**

- `GET /api/preferences` → `150`, `4`.
- `GET /api/plan/today` → `345`, with a 240-minute parent and 60- and 45-minute children.
- `app/mcp_server/src/services/tasks.py`, `get_today_plan` and `get_upcoming_plan`: `sum(t.estimated_minutes or 0 for t in tasks)` with no preference lookup.
- `app/web/app/page.tsx`, `const total = plan?.total_estimated_minutes ?? 0`.
- `app/web/components/task-group.tsx`, nested steps rendered inside the parent.
- Alexa replies from `POST /api/alexa-chat` on 2026-10-23.

**Impact:** The student sees a plan that is more than twice their stated capacity, and the voice assistant gives two different totals for the same day. The nesting makes the total ambiguous: is the parent estimate a rollup that already includes its steps, or a separate block? Without an answer, neither the UI nor Alexa can be trusted on time.

**Workaround used:** Asked Alexa for an overload check; it compared 345 minutes with the 150-minute preference. The web UI does not perform that comparison. I treated the parent task as a container and did not move data during the review.

**Actionable suggestion:**

- Decide and document effort semantics: either a parent estimate is a rollup and steps are excluded from the total, or a parent has its own effort and the UI must not nest the totals as if they were additive.
- Return `root_total_minutes` and `step_total_minutes` separately from plan endpoints.
- Make `get_today_plan` read `planning_preferences` and return `preferred_daily_minutes`, `over_preferred_minutes`, and a boolean `needs_rebalance`.
- Show an overload banner on Today when the plan exceeds the preference, with a “move work” action.
- Start Upcoming at tomorrow, or label it “7 days including today.”
- Use the same server-side total in the Alexa reply and the web UI so both surfaces agree.

---

## F-05 — “Since I last checked” has no last-checked state

**Area:** Inbox, change feed, Alexa context  
**Severity:** Medium

**Task attempted:** Ask exactly: “What changed since I last checked?”

**Steps taken:**

1. Sent the question through `/api/alexa-chat`.
2. Inspected the returned agent trace and the tool arguments.
3. Read the Inbox data loading and the change-feed tool.

**Expected:** Per the proposal, “Tell me what changed since I last checked” should not require opening every course and announcement page. The product should remember, or ask for, the student’s last check and show only what is new since then, ideally with an unread count.

**Actual:**

- The bridge called `study_get_changes_since` with no `since` argument.
- The reply mixed changes from October 20 and October 22 and then said “everything else is older.”
- The Inbox always requests `listChanges("limit=50")` and `listAcademicItems("limit=20")`; it has no unread or last-checked marker.
- No per-user read state is stored for the change feed. There is a source-level `last_seen_at` for ingestion, not an inbox read cursor.

**Evidence:**

- `POST /api/alexa-chat` trace: `study_get_changes_since` with empty arguments.
- `app/web/app/inbox/page.tsx`, `listChanges("limit=50")`.
- `app/mcp_server/src/mcp/tools/changes.py`, `since` is optional and defaults to no lower bound.
- `app/mcp_server/src/db/schema.py`, source and planning tables; no per-user inbox read marker.

**Impact:** The answer is useful but not actually “since I last checked.” A student cannot tell new items from old ones, and the Inbox has no unread signal. The feature works only when the student supplies a date.

**Workaround used:** Asked “What changed since yesterday?” The trace then used `study_get_changes_since` with `{"since":"2026-10-22"}` and produced a correctly scoped answer. Manually scanned dates in the Inbox.

**Actionable suggestion:**

- Store `last_checked_at` per student, or per source/connection if the product wants a more granular inbox.
- Default the Inbox to changes after `last_checked_at`, with a “show all” toggle.
- Add an unread count and mark-as-read action to the Inbox and sidebar.
- Let `study_get_changes_since` default to the student’s last check when `since` is omitted, and return `last_checked_at` in the response so Alexa can say what window it used.
- Add a test for the no-`since` path and for an explicit `since` path.

---

## F-06 — Course-page extraction produces noisy duplicates and loses dates and details

**Area:** Ingestion, extraction, review workflow  
**Severity:** High

**Task attempted:** Turn a labeled course HTML page into clean assignment records with usable due dates.

**Steps taken:**

1. Ran the extraction quality check on the `html_01_assignment` dataset case:

   ```powershell
   .\app\mcp_server\.venv\Scripts\python.exe test\test_extraction_quality.py --case html_01_assignment --no-report
   ```

2. Compared the returned candidates with the seven expected records.
3. Ran the smaller `email_01_assignment` case for contrast.

**Expected:** Per the proposal, the extraction step should convert source text into a restricted, structured academic record with titles, dates, weights, and evidence. A course page should produce a small set of assignment records, not a noisy candidate dump.

**Actual:**

- `html_01_assignment`: 7 expected records, 22 candidates, precision `0.32`, recall `1.00`, F1 `0.48`.
- Field pass rate: `details=0.14`, `due_at=0.57`.
- Several expected dates were missing, including “Micro-quiz 1,” “Homework 1,” “Project 1,” “Project 2,” and “micro-Quiz 2.”
- Duplicate or fragmented candidates appeared for project parts, for example “Project 1 … Part B,” “Project 2 … Part 2,” “Project 2 … Part 3,” and “Project 3 … First Review.”
- Extra readings and an “unclassified” item were returned alongside the graded work.
- `email_01_assignment` was cleaner but still returned 2 candidates for 1 expected record (F1 `0.67`).

This is a labeled sample from the repository, not a production source. The point is the pipeline behavior on a representative course page, not a judgment about one student’s data.

**Evidence:**

- The command output above, captured 2026-10-23.
- Dataset: `test/dataset/html_01_assignment/expected.json` and `input.html`.
- Extraction path: `app/mcp_server/src/ingestion/extraction.py` and `src/services/source_processing.py`.

**Impact:** The Inbox fills with duplicates and partial records, and the most important field for “what is urgent” — the due date — is missing on multiple assignments. The student must review and correct many records, which recreates the manual triage the product is supposed to remove. This is especially damaging for the trust promise: a missing date is less visible than a wrong date but just as harmful.

**Workaround used:** The intended workaround is the Inbox review/correction flow. For this review I compared the larger HTML case with the smaller email case and did not mutate data. The extraction pipeline itself ran successfully and produced evidence; the problem is precision and date recovery, not a crash.

**Actionable suggestion:**

- Deduplicate candidates before publishing: normalize title, collapse “Part 1/2/3” and “Part A/B” into a parent record or an explicit step list.
- Add a date-recovery pass that reads nearby date wording and fills `due_at` only when it is unambiguous; otherwise keep the item `uncertain` with a review reason.
- Publish high-confidence records and hold the rest as candidates, with counts on the source page.
- Add a minimum F1 gate per case to CI, not only an optional `--min-f1` flag.
- Add “details present” and “due date present” as explicit quality metrics in the report.

---

## F-07 — Source evidence exists in the API but is a placeholder in the web UI

**Area:** Provenance, source detail, web navigation  
**Severity:** Medium

**Task attempted:** Verify that a manual source submission can be followed to the original source, its revisions, and its extracted candidates.

**Steps taken:**

1. Traced the `/sources/new` submission and read the response shape, which returns `source_document_id`.
2. Looked for a link from the processing result to the source.
3. Opened `/sources/{source_document_id}` and called `GET /api/sources/{source_document_id}/candidates` for an existing source.
4. Checked the REST route inventory for a source list or detail endpoint.

**Expected:** Per the proposal’s trust section, “all the data that are formatted on the system will always reference to the original sources,” and the user should be able to view the original source clearly. A source detail view should show revisions, extracted candidates, review states, and links to the academic items it produced.

**Actual:**

- The processing result lists item counts but has no link to the source.
- `/sources/[source_document_id]` renders `PlannedView`, a branded placeholder; it does not fetch the source.
- `GET /api/sources` returns `404`; the route inventory marks the source list and source detail endpoints as “No.”
- The candidates endpoint exists at `GET /api/sources/{source_document_id}/candidates`, and item evidence exists at `GET /api/academic-items/{item_id}/evidence`, but the web app does not expose them together.

**Evidence:**

- `app/web/app/sources/[source_document_id]/page.tsx`, `PlannedView`.
- `app/web/app/sources/new/source-entry-form.tsx`, processing results without a source link.
- `app/mcp_server/src/api/app.py`, registered source routes.
- `system/STRUCTURE_BACKEND.md`, REST endpoint inventory marking source list/detail as not done.

**Impact:** A student or judge cannot follow the evidence trail from an extracted item back to the source page. The data exists, but the user-facing trust story is incomplete. Debugging extraction quality requires calling the API by hand.

**Workaround used:** Called `/api/sources/{id}/candidates` directly for an existing source and used the item detail page’s evidence section for individual records. The API returns candidates, evidence, review reasons, and date facts; only the UI route is missing.

**Actionable suggestion:**

- Implement `GET /api/sources` and `GET /api/sources/{source_document_id}`.
- Replace the source placeholder with a real detail view: revision history, candidate list with review states, and links to produced items.
- Link the source ID from the processing result and from each item’s evidence section.
- Add an “evidence” link on Inbox rows so the source trail is one click away.

---

## F-08 — The MCP server is local-only; there is no checked-in path to a real Alexa+ client

**Area:** Alexa+ integration, deployment, authentication  
**Severity:** High

**Task attempted:** Connect the study planner to a real Alexa+ client, or at least expose the MCP endpoint in a way an Alexa+ integration could reach.

**Steps taken:**

1. Read the proposal’s “MCP server to connect to Alexa+,” “Alexa+ Role,” and example conversation.
2. Inspected `app/mcp_server/src/api/app.py` and the startup scripts.
3. Checked the web app’s `/alexa+_simulator` and `/api/alexa-chat` path.
4. Checked the repository structure and frontend for an Alexa skill manifest, public MCP endpoint, or authentication layer.

**Expected:** Per the proposal, Alexa+ is the conversational controller between the student and the system. The MCP server should be connectable by the Alexa+ client, which implies a reachable, authenticated endpoint and an integration path.

**Actual:**

- The API listens on `127.0.0.1:8001` and the MCP server on `127.0.0.1:8000` by default.
- The README explicitly says there is no student authentication yet and the API must remain local.
- The only conversational client is the local `/alexa+_simulator` page, which posts to `/api/alexa-chat`; the browser never reaches MCP directly.
- No Alexa skill manifest, request/response adapter, or public deployment configuration is checked in.
- The simulator is useful, but it is not evidence that a real Alexa+ client can reach and authenticate the server.

**Evidence:**

- `app/mcp_server/src/api/app.py`, `uvicorn.run(..., host="127.0.0.1", port=args.port)`.
- `app/README.md`, the note that the backend has no student authentication and must stay on loopback.
- `app/web/lib/mcp-client.ts`, the server-side MCP client and default URL.
- `app/web/app/alexa+_simulator/`, the local simulator.
- `system/PROJECT_PROPOSAL.md`, “MCP server to connect to Alexa+.”

**Impact:** The core integration cannot be validated end to end. A demo that works only through the simulator may still be acceptable for a hackathon, but the proposal describes an Alexa+ product. Without a public, authenticated endpoint, the MCP server cannot be connected to a real Alexa+ client safely.

**Workaround used:** Used the local simulator and called `/api/alexa-chat` directly. Did not expose the loopback API or use a tunnel, because the API has no auth boundary.

**Actionable suggestion:**

- If Alexa+ integration is in scope: add an authentication boundary, deploy the MCP endpoint over HTTPS, and check in the Alexa skill/manifest or adapter that connects to it.
- If the simulator is the intended submission scope: say so explicitly in the README and proposal status, and label the simulator as the supported client.
- Add `/health` and `/ready` endpoints so an external client can verify reachability before a conversation.
- Add an integration test that starts the server, connects a client over the chosen transport, and lists the `study_*` tools.

---

## F-09 — Google Classroom and the time constraints needed for a “realistic” plan are absent

**Area:** Source coverage, availability model, planning inputs  
**Severity:** High

**Task attempted:** Verify whether Google Classroom can be connected and whether the planner can generate a realistic plan around classes, a work shift, a commute, and sleep preferences.

**Steps taken:**

1. Read the proposal’s source list: Gmail, Google Classroom, and manual entry.
2. Opened `app/mcp_server/src/connectors/classroom.py`.
3. Checked the connector hub and the database schema for Classroom, calendar, work, commute, sleep, or availability concepts.
4. Traced the inputs used by `get_today_plan` and the Alexa planning prompt.

**Expected:** Per the proposal, Google Classroom is a core source, and a realistic today plan must “account for classes, work shifts, commute, sleep preferences, existing calendar events, and available study time.”

**Actual:**

- `connectors/classroom.py` contains only a docstring: “Reserved for a future Google Classroom connector.”
- The connectors hub lists only Gmail.
- The schema has sources, courses, academic items, tasks, and planning preferences; it has no calendar, class schedule, work shift, commute, sleep, or availability table.
- The plan service reads tasks and selected days; preferences are stored but not applied by the plan endpoints.
- Alexa can reason about constraints only if the student states them in the conversation; there is no durable availability context.

**Evidence:**

- `app/mcp_server/src/connectors/classroom.py`.
- `app/web/app/connecters/page.tsx`, only the Gmail card.
- `app/mcp_server/src/db/schema.py`, model list.
- `app/mcp_server/src/services/tasks.py`, plan queries.
- `system/PROJECT_PROPOSAL.md`, “Common Tools to Receive Uni Data” and “Give me a realistic plan for today.”

**Impact:** The planner is a task list with a chat layer, not yet a realistic schedule. It cannot know that a student has class from 10:00–12:00, work from 16:00–22:00, or a 45-minute commute. A plan that ignores those constraints can recommend work at times the student cannot use.

**Workaround used:** Manual source upload and stating constraints in the chat are the available workarounds. For this review I used existing data and code inspection; I did not connect a live Classroom account or rely on the planner to discover a routine.

**Actionable suggestion:**

- Implement the Classroom connector or remove it from the MVP source list and mark it as future work.
- Add availability windows (class, work, commute, sleep) and, if possible, calendar import.
- Include availability in the plan response and in the planning prompt; ask for missing constraints instead of assuming a free day.
- Add a `PUT /api/availability` endpoint and an MCP read so Alexa can persist and use the student’s routine.

---

## F-10 — Alexa refuses to delete or merge, while the web UI can delete

**Area:** Voice editing, capability boundaries, task management  
**Severity:** Medium

**Task attempted:** Ask Alexa to remove one of two duplicate tasks, a natural request when the Inbox contains duplicates from extraction.

**Steps taken:**

1. Sent a hypothetical request through `/api/alexa-chat`: “If I had two duplicate tasks, could you delete one of them for me?”
2. Inspected the tool trace and the system prompt.
3. Checked the web task actions and the MCP task tools.

**Expected:** The voice assistant and the web UI should expose a coherent set of task operations. If Alexa cannot delete, it should say so and point to the web action, or offer a supported alternative with clear confirmation.

**Actual:**

- Alexa replied: “I can't delete tasks, so I'd leave both duplicates as they are. If you'd like, I can update one of them instead, like renaming it or moving it to a different day.”
- The trace contained no tool calls, which is the intended safe behavior.
- `CHAT_SYSTEM_PROMPT` explicitly says the planner has no delete or merge tool and forbids emulating one.
- The web task card has a delete button and `DELETE /api/tasks/{task_id}` exists.

**Evidence:**

- The simulated conversation on 2026-10-23.
- `app/web/lib/mcp-client.ts`, capability-boundary prompt.
- `app/mcp_server/src/mcp/tools/tasks.py`, no delete tool.
- `app/web/components/task-actions.tsx` and `app/web/app/api/tasks/[task_id]/route.ts`, web deletion.

**Impact:** Duplicates are common after extraction, and “remove one” is exactly the cleanup the student wants. The refusal is truthful and safe, but it creates a capability split: the web can delete, voice cannot. The assistant could at least offer “delete it from the task page” with a link.

**Workaround used:** The web delete button and `DELETE /api/tasks/{task_id}` are available; I verified both but did not delete demo data. Non-destructive updates and moves work through Alexa.

**Actionable suggestion:**

- If deletion is in scope, add `study_delete_task` with an explicit confirmation argument and an audit trail; if it is out of scope, keep the refusal but add a deep link to the web task.
- Document the voice/web capability split in the README and the simulator help text.
- Add a merge operation only if the data model supports it; otherwise offer “keep one, mark the other done” as an explicit, clearly labeled choice, not as a silent workaround.
- Add a regression test that forbids using completion or review-state changes to simulate deletion.

---

## F-11 — Connectors route is misspelled, and lint warnings remain

**Area:** Frontend routing, developer polish  
**Severity:** Low

**Task attempted:** Open the Connectors page at the URL a user would naturally try, then run the frontend checks.

**Steps taken:**

1. Requested `/connectors` and `/connecters`.
2. Ran `npm run lint`.
3. Ran `npm run build`.

**Expected:** The route matches the navigation label “Connectors,” and the project is lint-clean.

**Actual:**

- `/connectors` → `404`; `/connecters` → `200`.
- The sidebar and connector links consistently use `/connecters`, so the app works, but the misspelling is visible in the URL and in every internal link.
- `npm run lint` reports three warnings:
  - `requestFromBridge` is defined but never used in `app/alexa+_simulator/alexa-transport.ts`.
  - `Link` is imported but unused in `app/connecters/gmail/page.tsx`.
  - `Link` is imported but unused in `app/sources/new/page.tsx`.
- `npm run build` succeeds, so none of this blocks the demo.

**Evidence:**

- `/connectors` → `404`, `/connecters` → `200` on 2026-10-23.
- `npm run lint` output: 0 errors, 3 warnings.
- `npm run build`: 25 routes generated successfully.

**Impact:** Low: the sidebar works, and the warnings do not block the build. The misspelling is a credibility issue in a demo URL, and unused imports add noise for contributors.

**Workaround used:** Used the sidebar and `/connecters`. Ignored the warnings for runtime testing.

**Actionable suggestion:**

- Add a permanent redirect from `/connectors` to `/connecters` now, and rename the route to `/connectors` when the internal links can be updated together.
- Remove the unused `Link` imports and the dead `requestFromBridge` helper, or wire the helper into the transport.
- Run `npm run lint` in CI and make warnings fail the check once the tree is clean.

---

## What worked well

The review was not only negative. The following parts were stable and worth keeping:

- **Backend integration tests:** `uv run python -m unittest tests.test_mcp_server -v` passed all 10 tests in 21.9 seconds.
- **Frontend production build:** `npm run build` completed successfully and generated 25 routes.
- **MCP surface:** The `study_*` tools and resources are registered and discoverable; task CRUD, plan views, courses, items, changes, preferences, sources, and Gmail operator tools are present.
- **Alexa bridge:** The simulator called the right read tools for plan, changes, and urgency questions; responses arrived in roughly 3.7–11.3 seconds in this environment. Read-only prompts stayed read-only.
- **Truthfulness guard:** The bridge has a claim verifier and a capability-boundary prompt; when asked to delete a duplicate, it refused instead of pretending to delete it.
- **Extraction pipeline:** Manual text, HTML, and PDF ingestion run end to end; evidence and review states are persisted; Gmail ingestion has cursor, retry, and lease handling.
- **Inbox and course UI:** The change feed, academic item detail, course board, task views, and preferences form are functional; the remaining gaps are about semantics, source visibility, and automatic planning rather than broken CRUD.

## Recommended fix order

| Order | Fix | Why first |
| --- | --- | --- |
| 1 | F-01, F-02 | A new user must be able to start the app and see Gmail work without environment/port confusion or contradictory docs. |
| 2 | F-08 | Decide whether the submission is a simulator demo or a real Alexa+ integration; this affects the demo story and security scope. |
| 3 | F-03, F-04 | The core promise is an actionable, realistic plan. Today must be consistent and deadline changes must propagate. |
| 4 | F-06, F-07 | The plan is only as good as the extracted records and the evidence trail. |
| 5 | F-05 | “What changed since I last checked” needs state, not just a feed. |
| 6 | F-09 | Classroom and availability are large scope items; implement or explicitly defer them. |
| 7 | F-10, F-11 | Polish the voice/web capability split and the route/lint issues. |

## Appendix — raw command evidence

```text
$ uv run python -m unittest tests.test_mcp_server -v
Ran 10 tests in 21.905s

OK
```

```text
$ npm run build
▲ Next.js 16.3.8 (Turbopack)
✓ Compiled successfully in 7.8s
✓ Generating static pages using 11 workers (25/25)
```

```text
$ npm run lint
✖ 3 problems (0 errors, 3 warnings)
- 'requestFromBridge' is defined but never used
- 'Link' is defined but never used (gmail page)
- 'Link' is defined but never used (sources/new page)
```

```text
GET /api/preferences
{ "preferred_daily_minutes": 150, "focus_task_count": 4 }

GET /api/plan/today
{ "day": "2026-10-23", "total_estimated_minutes": 345, "tasks": [ ... ] }
```

```text
$ .\app\mcp_server\.venv\Scripts\python.exe test\test_extraction_quality.py --case html_01_assignment --no-report

html_01_assignment  [OK]  expected=7 candidates=22  P=0.32 R=1.00 F1=0.48
field pass-rate: details=0.14  due_at=0.57
TOTAL  expected=7 candidates=22 matched=7  micro P=0.32 R=1.00 F1=0.48
```

```text
GET /api/sources              → 404
GET /api/plan/kanban          → 404
GET /connectors               → 404
GET /connecters               → 200
```

No API keys, OAuth tokens, email addresses, or raw source contents are reproduced in this log.
