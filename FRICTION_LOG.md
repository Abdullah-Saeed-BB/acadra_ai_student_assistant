# Acadra Friction Log

| Item                | Value                                                                                                                                                                                                                                                |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Date                | 2026-10-26                                                                                                                                                                                                                                           |
| Session             | 1 — live end-to-end pass                                                                                                                                                                                                                             |
| Project             | Acadra — AI academic assistant for university students                                                                                                                                                                                               |
| Scope               | The three headline student jobs — “what changed since I last checked”, “what is actually urgent”, and “a realistic plan for today” — plus setup, extraction, and source management. |
| Severity Scale      | **Low** (annoyance, doesn't block work), **Medium** (slows down work, workaround exists), **High** (blocks progress)                                                                                                                                 |
| Investigation setup | The product was run locally and exercised end to end through its real surfaces: the REST API, the MCP server, the Alexa+ bridge, and the web pages. The backend integration tests were also run.                                                     |
| Notes               | This is the project’s first friction log, not a bug bounty. Entries that rely on code rather than a live run say so in a **Verification** line. Test records were cleaned up and the pre-review database counts restored (see [Cleanup](#cleanup)).  |

## Summary

| ID   | Task attempted                                            | Area                 | Severity   | Workaround                                |
| ---- | --------------------------------------------------------- | -------------------- | ---------- | ----------------------------------------- |
| F-01 | Turn a pasted course announcement into a dated assignment | Extraction           | **High**   | Edit the due date by hand                 |
| F-02 | Open Today and Upcoming and see what to do                | Planning / views     | **High**   | Scan All tasks for old dates              |
| F-03 | Ask “what changed since I last checked?”                  | Inbox / Alexa        | **High**   | Name an explicit date                     |
| F-04 | Check that plan totals mean *remaining* work              | Planning / views     | **Medium** | Subtract finished work mentally           |
| F-05 | Ask “which assignment is actually the most urgent?”       | Priority / Alexa     | **Medium** | Ask it to compare specific items          |
| F-06 | Ask for a plan inside a 45-minute gap                     | Alexa / planning     | **Medium** | Ask for one smaller task                  |
| F-07 | Inspect or remove the source behind an item               | Provenance / sources | **Medium** | Delete the item; SQL to remove the source |
| F-08 | Run extraction with a non-Groq provider                   | Configuration        | **Medium** | Keep Groq configured                      |
| F-09 | Use the Alexa+ simulator as a voice assistant             | Alexa bridge         | **Medium** | Keep prompts short; retry the turn        |
| F-10 | Follow docs and links from a clean checkout               | Documentation        | **Low**    | Read the code                             |
| F-11 | Get the same “today” in the API and the bridge            | Time handling        | **Low**    | Pass the day explicitly                   |
| F-12 | Run the test suite and read its result                    | Developer experience | **Low**    | Suppress stderr; ignore exit code         |

---

## F-01 — A deadline is parsed and then thrown away by the evidence validator

**Area:** Ingestion / extraction, academic items
**Severity:** High

**Task attempted:** Paste a realistic course announcement and get an assignment record with a usable deadline, so the planner can schedule it.

**Steps taken:**

1. Posted this text to `POST /api/sources/text` (title: “FRICTION TEST – DB102 assignment announcement”):

   > Databases (DB102) announcement. Assignment 2: SQL joins and aggregation is now available. It is due Friday 30 October 2026 at 23:59 and is worth 20% of your final grade. Submit it on Google Classroom. Late submissions lose 10% of the mark per day.

2. Waited for extraction (`processing_status: processed`, 19.9 s, 1 item, `review_count: 1`).
3. Read the created item and `GET /api/sources/{id}/candidates`.
4. Reproduced the decision without the model by calling `normalize_candidate()` with three evidence variants.

**Expected:** The deadline `2026-10-30 23:59` should be stored, or stored with an explicit review flag that keeps the parsed value visible, so the assignment can be scheduled and prioritised.

**Actual:**

- The item was created with `due_at: null`, `review_state: "uncertain"`, and review reason `due_at: source evidence is missing`.
- The candidate **did** contain the parsed date: `date_facts.due_at.value = "2026-10-30T23:59"`, `precision: "datetime"`.
- The validator compares the model’s evidence quote with the source text and requires a literal substring **and** a timezone token in that quote (`src/ingestion/extraction.py:232-260`). The model returned the normalized ISO value as evidence, so the literal check failed. A typical announcement with no stated timezone fails the timezone check even with perfect evidence.

Deterministic check (`normalize_candidate`, source text with/without “UTC”):

| Evidence quote supplied | Result |
| --- | --- |
| `Friday 30 October 2026 at 23:59` (literal, no timezone) | `due_at=None`, reason: `time zone is not in source evidence` |
| `Friday 30 October 2026 at 23:59 UTC` (literal + timezone) | `due_at=2026-10-30 23:59:00+00:00`, no reasons |
| `2026-10-30T23:59:00+00:00` (normalized, what the model returned) | `due_at=None`, reason: `source evidence is missing` |

**Evidence:**

- Live response: item `due_at: null`, `review_state: "uncertain"`; candidates include `"due_at": {"value": "2026-10-30T23:59", "precision": "datetime", "wording": "2026-10-30T23:59"}`.
- `app/mcp_server/src/ingestion/extraction.py:232-260` (`_supported_evidence`, `_date_value`), `:288-289`, `:313-318`.
- Item page (`/items/{id}`) renders “Due **No date**” directly above details that say “It is due Friday 30 October 2026 at 23:59”.

**Impact:** The most important field in the product is dropped at the validation step, for the most common phrasing (“due Friday 30 October at 23:59”). Everything downstream inherits the gap: the item cannot be ranked as urgent, Today cannot plan backwards from the deadline, Upcoming cannot warn about a bad week, and the student must retype a date the system already understood. The assistant is put in the position of quoting the date from unstructured details while the record says “No date”.

**Workaround used:** Edit the item’s **Due** field on the item page (the UI converts local time to an ISO instant correctly), or state the date explicitly to Alexa. For this review I read the value from `date_facts` and then removed the test source.

**Actionable suggestion:**

- Keep the parsed value when validation is uncertain: store `due_at` with a `precision` / `needs_review` flag instead of `NULL`, and mark the item for review. A date that is 90% right is more useful than no date, provided the UI labels it as unconfirmed.
- Validate either form of evidence: accept a literal quote, or an ISO value that matches the parsed datetime, and keep the literal wording separately for the evidence panel.
- Add a student timezone setting (see F-11) and use it for announcements that give a wall-clock time with no zone, instead of rejecting the date.
- On the item page, show “Parsed: 30 Oct 2026, 23:59 — confirm” with one click, rather than an empty field.
- Add unit tests for the four cases above: no timezone, date-only, normalized evidence, conflicting dates.

---

## F-02 — 24 overdue tasks are invisible on Today and Upcoming

**Area:** Today / Upcoming, task plan semantics
**Severity:** High
**Task attempted:** Open the app on 2026-10-26 and see what to work on today and this week.

**Steps taken:**

1. `GET /api/plan/today`
2. `GET /api/plan/upcoming?days=7`
3. `GET /api/tasks?limit=100` and grouped the results by `selected_day`
4. `GET /api/plan/overdue` (does not exist)
5. Opened `/` and `/inbox`
6. Later, asked Alexa to “Plan a light day for tomorrow” and inspected what it moved

**Expected:** Unfinished work from previous days stays visible. A task should not become complete just because its selected day passed, and the Today/Upcoming views should surface outstanding old work so the student can reschedule it.

**Actual:**

- `/api/plan/today` → `{"day":"2026-10-26","total_estimated_minutes":0,"tasks":[]}`.
- `/api/plan/upcoming?days=7` → seven days, every one `0` minutes.
- `/api/tasks?limit=100` → **24 of 26** unfinished tasks are scheduled on 2026-10-19 … 2026-10-25. The other 2 are Backlog.
- `/api/plan/overdue` → `404`.
- The Today page says: “Nothing is planned for today yet.”
- When Alexa moved the step “Write demonstration queries” to 2026-10-27, its parent “Database assignment: Restaurant database” stayed on 2026-10-23. `GET /api/tasks` then showed a step scheduled tomorrow whose parent is still overdue. In the Upcoming view, `task-group.tsx` groups tasks by parent only when the parent is in the same day’s list, so the step renders as a standalone card (code path: `app/web/components/task-group.tsx:36-49`).

**Evidence:**

- Plan responses above, captured 2026-10-26.
- `app/mcp_server/src/api/app.py:121-123` registers only `today`, `upcoming`, and `backlog`; there is no overdue route.
- `app/mcp_server/src/services/tasks.py:546-566`, `:569-596`: exact-day and forward-only queries.
- `app/web/components/task-group.tsx:36-49`.

**Impact:** A student who trusts the landing page believes the week is free while 24 obligations are unresolved. Alexa compounds it: with an empty Today plan, it falls back to the Backlog and recommends work that was never scheduled. The “bad week” warning cannot work on a view that starts today and ignores everything before it.

**Workaround used:** Opened **All tasks** and read the dates manually. Asked Alexa about specific days. Moved nothing permanently.

**Actionable suggestion:**

- Add overdue semantics to the plan service: `GET /api/plan/overdue`, and include an `overdue` group or count in `/api/plan/today` and the Today page (“24 tasks are past their day — review”).
- Decide the roll-over rule explicitly: show overdue work in Today by default, or show a banner with a one-click “move to today”; do not silently drop it.
- When a step is moved, return its parent context in the response and keep the parent on the card (“step of: Database assignment”), with an option to move the whole assignment.
- Start Upcoming at tomorrow and label it clearly, or keep today and document it; today currently appears in both Today and Upcoming.
- Add a test seeded with past `selected_day` values and assert that `/api/plan/today` (or its overdue block) surfaces them.

---

## F-03 — “What changed since I last checked?” has no last-checked anchor

**Area:** Inbox / change feed / Alexa context
**Severity:** High

**Task attempted:** Ask the headline job exactly: “What changed since I last checked?”

**Steps taken:**

1. `POST /api/alexa-chat` with that one user message.
2. Inspected the returned `trace.steps[*].toolCalls`.
3. `GET /api/changes?limit=24` and counted the real events.
4. Read `app/web/app/inbox/page.tsx` and `src/mcp/tools/changes.py`.

**Expected:** The answer covers the window since the student’s last visit and names that window, so the student does not have to open every course, announcement page, email thread, and calendar.

**Actual:**

- The bridge called `study_get_changes_since` with `{"since":"2026-10-26"}` — today. It reported one new item: “Since you last checked, one new item appeared: Assignment 2: SQL joins and aggregation … It’s still marked as uncertain.”
- The database held **15** change events, dated 2026-10-22 and 2026-10-23.
- There is no stored read cursor: `source_documents.last_seen_at` is ingestion time, not student read time. The Inbox always requests `listChanges("limit=50")` and `listAcademicItems("limit=20")` with no window.
- `since` is optional in the tool schema, so the model had to invent an anchor; “today” is a reasonable guess and a wrong answer.

**Evidence:**

- Bridge trace: `study_get_changes_since` with `since: "2026-10-26"`; reply quoted above.
- `app/web/app/inbox/page.tsx:83-85`.
- `app/mcp_server/src/mcp/tools/changes.py:34-57`.
- `app/mcp_server/src/db/schema.py:70` (`last_seen_at` belongs to source ingestion).

**Impact:** The product answers its own headline question incorrectly and confidently. A student who checks once a week misses 14 of 15 changes. The wording “since you last checked” makes the wrong window sound authoritative.

**Workaround used:** Asked “What changed since October 22?” and manually scanned the Inbox dates. The Inbox itself is useful; only the “last checked” anchor is missing.

**Actionable suggestion:**

- Store `last_checked_at` (per student, or per conversation if there is no auth yet) and update it when the Inbox opens or when a conversation starts.
- Default `study_get_changes_since` and `GET /api/changes` to that cursor, and return `since` / `last_checked_at` in the response so Alexa can say “since your last visit on 23 October”.
- Add an unread count to the Inbox and sidebar, plus a “mark all as read” action.
- Add tests for the no-`since` path (must use the cursor) and the explicit-`since` path.

---

## F-04 — Plan totals count completed work, and the plan service never applies preferences

**Area:** Planning / workload math
**Severity:** Medium

**Task attempted:** Check that “today’s effort” and “upcoming workload” mean remaining work.

**Steps taken:**

1. Moved a 60-minute task to 2026-10-27 (through Alexa) and read `/api/plan/upcoming?days=7`.
2. Patched the task to `status: "done"` with `PATCH /api/tasks/{id}`.
3. Read `/api/plan/upcoming?days=7` again.
4. Reverted the task to `todo`.
5. Read `get_today_plan`, `get_upcoming_plan`, and `services/preferences.py`.

**Expected:** Completed work is excluded from remaining effort, or reported separately. Saved preferences (`preferred_daily_minutes: 150`, `focus_task_count: 4` in this database) are used to mark a day as over budget.

**Actual:**

- Before: 2026-10-27 → `60m`, one `todo` task.
- After marking it done: 2026-10-27 → still `60m`, one `done` task.
- `get_today_plan` and `get_upcoming_plan` filter only by `selected_day`; neither filters `status` (`src/services/tasks.py:558-563`, `:575-580`).
- The task service does not import the preferences service (`grep` finds no `preferences` reference in `services/tasks.py`), so the 150-minute default has no effect on any plan endpoint.

**Evidence:**

- API responses above, captured 2026-10-26.
- `app/mcp_server/src/services/tasks.py:546-596`.
- `app/mcp_server/src/services/preferences.py` (storage only; consumers are the MCP tool and REST route).

**Impact:** The number on Today does not fall as the student works, so “remaining work” is overstated. Any warning about a bad week built on these totals will be wrong. The saved preference looks like it works (the Settings page accepts it) but changes nothing.

**Workaround used:** Mentally subtracted finished tasks; did not rely on the total.

**Actionable suggestion:**

- Return three numbers from plan endpoints: `planned_minutes`, `completed_minutes`, `remaining_minutes` (todo + in_progress). Display remaining as the headline and completed as progress.
- Apply `preferred_daily_minutes` in the plan response (`over_budget_minutes`, `needs_rebalance`) and show a banner on Today.
- Exclude `done` tasks from the plan cards by default, with a “show completed” toggle.
- Add tests for a day that contains a done task and a todo task.

---

## F-05 — “What is actually urgent?” is a single LLM judgement, not a system calculation

**Area:** Priority / Alexa reasoning
**Severity:** Medium

**Task attempted:** Ask “Which assignment is actually the most urgent right now, and why?”

**Steps taken:**

1. `POST /api/alexa-chat` with that question.
2. Inspected the tool trace.
3. Read the academic-item fields and the services that use `grade_weight_percent` / `late_penalty`.

**Expected:** “Urgent” should reflect more than the nearest date: grade value, time required, dependencies, late penalties, and current workload should influence the answer.

**Actual:**

- The bridge made **one** tool call: `study_list_academic_items` with `item_type: "assignment"`, `limit: 50`.
- Reply: “The most urgent one is ‘Programming assignments’ — it’s due Friday, October 30 … Everything else either has no due date yet or isn’t due until next year.”
- It ranked by nearest known due date only. It did not read tasks, remaining effort, or workload, and it did not compare grade weight or late penalty.
- The fields exist (`academic_items.grade_weight_percent`, `late_penalty`), and are returned by the item tools, but no service consumes them for ordering or scoring (`grep` across `src/` finds storage, serialization, and validation only).
- 11 of the 13 academic items in this database have `due_at = NULL` (partly F-01), so they were excluded from the comparison entirely.

**Evidence:**

- Bridge trace: one round, `study_list_academic_items`, 16,075 tokens, 24.7 s.
- Reply quoted above.
- `app/mcp_server/src/db/schema.py:154-155` (fields); `src/services/academic_items.py` (CRUD only).
- `app/mcp_server/src/services/tasks.py` (no ranking).

**Impact:** “Urgent” means “earliest known date” and silently drops work with missing dates — which is the majority of records. Two runs can produce different answers because the ranking is model reasoning, not product logic. The distinction between “due soon” and “actually important” is not implemented as behavior.

**Workaround used:** Asked for explicit comparisons and passed weights in the prompt. Results were plausible but not repeatable.

**Actionable suggestion:**

- Add a deterministic priority service: `study_get_priority_items(limit, horizon_days)` returning `score`, `rank`, and `score_components` (due proximity, grade weight, late penalty, remaining effort, dependency, workload).
- Treat a missing due date as a risk factor, not as “not urgent”; include it with a “date unknown — review” label.
- Include linked task effort in the item payload or the scoring service, so “time required” is real.
- Have the bridge call the scoring tool for urgency questions instead of re-ranking in the prompt; keep the explanation in the tool response.

---

## F-06 — A 45-minute study gap produces a 75-minute plan

**Area:** Alexa planning / time budget
**Severity:** Medium

**Task attempted:** Ask for a study plan that fits a 45-minute gap: “Alexa, I have 45 minutes before my next class. What should I study?”

**Steps taken:**

1. Sent exactly that message through `POST /api/alexa-chat`.
2. Read the reply and added the suggested minutes.
3. Inspected the tool trace.

**Expected:** Suggestions total at most 45 minutes, chosen from what is actually due/urgent.

**Actual:**

- Reply: “You could spend the next 45 minutes tackling your backlog: start the ‘Write demonstration queries’ task for about 30 minutes, then finish the ‘Test and finalize submission’ task (30 minutes total) and use the remaining 15 minutes to continue the queries.”
- The arithmetic is 30 + 30 + 15 = **75 minutes**, and the two items are Backlog steps, not today’s planned work. Today was empty (F-02).
- Latency for this turn: 115.7 s (cold), 12,533 tokens, 3 rounds.

**Evidence:**

- Reply and trace above, captured 2026-10-26.
- `app/web/lib/mcp-client.ts:930-980` (planning rules in the prompt; no budget enforcement).
- `src/services/tasks.py` has no “plan for N minutes” operation.

**Impact:** The 45-minute scenario fails on its own constraint. In a real gap the student either starts too much or has to re-plan, which recreates the overload the product exists to remove.

**Workaround used:** Asked for “one 30-minute task” and ignored the 30-minute overrun. No writes were made in this turn.

**Actionable suggestion:**

- Add a deterministic `study_plan_for_budget(minutes)` that selects tasks whose estimates sum within the budget (and respects the daily preference), returning the chosen tasks and `remaining_minutes`.
- If the bridge keeps composing plans, pass the budget into the prompt as a hard constraint and post-check the sum against it before replying.
- Prefer Today/overdue work before Backlog work in a time-gap answer.
- Add a regression test that sums the minutes in the final reply and fails above the stated budget.

---

## F-07 — Sources cannot be listed, opened, or deleted through the product

**Area:** Provenance / source management
**Severity:** Medium

**Task attempted:** Follow an extracted item back to its original source, and remove a bad test upload.

**Steps taken:**

1. `GET /api/sources`
2. `GET /api/sources/{source_document_id}`
3. `DELETE /api/sources/{source_document_id}`
4. Opened `/sources/{source_document_id}`
5. Read `src/services/sources.py`, `src/api/app.py`, and the MCP source tools.
6. After the review, removed the test source directly in PostgreSQL.

**Expected:** A student or judge should be able to open the source, see its revisions/candidates, and remove a mistaken upload, so every extracted record can be traced back to the material that produced it.

**Actual:**

- `GET /api/sources` → `404`.
- `GET /api/sources/{id}` → `404`.
- `DELETE /api/sources/{id}` → `404`.
- `/sources/{source_document_id}` renders `PlannedView` (a branded placeholder).
- The MCP server has read-only `study_list_sources` / `study_get_source_detail`, and the candidates/evidence endpoints work; there is no delete in any layer.
- Removing one test source required direct SQL across six tables because there are no cascades: `academic_item_changes`, `source_item_links`, `source_processing_runs`, `academic_items`, `source_revisions`, `source_documents` (plus restoring the moved task).

**Evidence:**

- Status codes above, 2026-10-26.
- `app/web/app/sources/[source_document_id]/page.tsx:1-15` (`PlannedView`).
- `app/mcp_server/src/api/app.py:99-102` (only text/file intake and candidates).
- `app/mcp_server/src/db/schema.py` (foreign keys without `ondelete`).

**Impact:** A mistaken upload or an extraction experiment stays in the database forever, and the web app has no way to audit the source trail that the trust story depends on. Demo databases accumulate junk. Cleaning up requires database access, which a student never has.

**Workaround used:** Deleted the produced academic item via `DELETE /api/academic-items/{id}` (this works), then removed the source rows with SQL and verified the original row counts.

**Actionable suggestion:**

- Implement `GET /api/sources` and `GET /api/sources/{source_document_id}` (services already exist for MCP), and replace the placeholder page.
- Add `DELETE /api/sources/{source_document_id}` with either a soft delete (`archived_at`) or a transactional cascade; report how many items/revisions/links were removed.
- Link the source from the item evidence panel and from the Inbox change row.
- Add the source list and detail to the “REST endpoint inventory” as done when they land.

---

## F-08 — “Any AI provider you prefer” fails the Groq-only ingestion gate

**Area:** Configuration / extraction
**Severity:** Medium

**Task attempted:** Run extraction with the provider configured in `.env` when it is not Groq, as the README allows.

**Steps taken:**

1. Read `app/README.md`: “**Groq API key** _(Or any AI provider you prefer)_ for extraction and the Alexa+ bridge”.
2. Read the provider switch in `src/ingestion/extraction.py:190-219` (supports `openrouter` and OpenAI-compatible endpoints).
3. Read the configuration check in `src/services/source_processing.py`.
4. Compared with `MODEL_PROVIDER` in `.env.example`.

**Verification:** code path only; I did not run extraction with an alternate provider key.

**Expected:** The “configured” check follows `MODEL_PROVIDER`: OpenRouter with `OPENROUTER_API_KEY` is a valid setup, and extraction either runs or reports a provider-specific error.

**Actual:**

- `src/services/source_processing.py:147` hard-codes:
  `if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "API_KEY": return ProcessingResult("pending_configuration", [])`.
- With `MODEL_PROVIDER=openrouter` and a valid `OPENROUTER_API_KEY` but no Groq key, every manual source returns `pending_configuration` even though `extract_academic_candidates` would work.
- The message does not name the missing key or the provider, so the cause is not visible in the UI.

**Evidence:**

- `app/mcp_server/src/services/source_processing.py:147-148`.
- `app/mcp_server/src/ingestion/extraction.py:190-219`.
- `app/README.md:33`, `app/mcp_server/.env.example:11-14`.

**Impact:** A supported configuration looks broken. Anyone evaluating with an OpenAI/OpenRouter/DeepSeek key hits a dead end and may conclude extraction is unimplemented.

**Workaround used:** Kept Groq configured for this review. (`MODEL_PROVIDER=groq` with a real `GROQ_API_KEY` works.)

**Actionable suggestion:**

- Add a shared `model_config.is_configured()` that reads `MODEL_PROVIDER` and checks the matching key; use it in source processing, Gmail ingestion, and the bridge.
- Return the provider and the missing variable name in `pending_configuration` (“Set OPENROUTER_API_KEY or switch MODEL_PROVIDER”).
- Add one integration test per provider that asserts `pending_configuration` only when that provider’s key is missing.

---

## F-09 — The Alexa+ bridge takes 15–116 seconds per turn

**Area:** Alexa bridge / performance
**Severity:** Medium

**Task attempted:** Use `/alexa+_simulator` as a stand-in for a voice assistant across four realistic asks.

**Steps taken:**

1. Sent four prompts through `POST /api/alexa-chat` and recorded wall-clock time and token usage from the trace.
2. Counted the discovered tools and the prompt tokens in the first round.

**Expected:** A conversational answer in a few seconds, suitable for voice.

**Actual:**

| Prompt | Wall time | Total tokens | Rounds |
| --- | --- | --- | --- |
| “I have 45 minutes before my next class. What should I study?” (cold) | 115.7 s | 12,533 | 3 |
| “What changed since I last checked?” | 15.4 s | 18,010 | 2 |
| “Plan a light day for tomorrow.” | 98.4 s | 42,148 | 5 |
| “Which assignment is actually the most urgent right now, and why?” | 24.7 s | 16,075 | 2 |

- The bridge discovers 27 `study_*` tools and sends all their schemas on every round; a simple Today read used 3,861 prompt tokens in round 1.
- `MAX_TOOL_ROUNDS = 10` (`app/web/lib/mcp-client.ts:928`); “Plan a light day” used five rounds, including a full task read.
- The dev-server log shows the dominant cause of the worst turns: the primary OpenRouter model failed repeatedly, and the retry budget (60 s per attempt, up to 3) stretched individual rounds to 40–72 s. For example, one round logged three failed attempts (cumulative 40.3 s) before the Groq fallback answered in 6.3 s; another spent 60.0 s on a timeout and 5.9 s on the successful retry (cumulative 65.9 s). The 98.4 s turn’s fourth round took 72.1 s, of which 57.9 s was the failed first attempt. `completeChat` allows `MODEL_MAX_RETRIES + 1` attempts per round (60 s timeout each), and a turn can contain several rounds (`app/web/lib/mcp-client.ts:1091-1214`).
- The trace keeps only the model that answered (`trace.model` changes on fallback), so the returned `trace.steps` shows success and hides the failed attempts; the failures are visible only in the Next.js server console.

**Evidence:**

- Timings and traces above, 2026-10-26.
- `app/web/lib/mcp-client.ts:422-456` (every tool schema is sent each round), `:1091-1214` (retry loop and per-attempt timeout), `:928`.
- Next.js dev log, 2026-10-26: `chat-completions network error (attempt 1/3) … fetch failed`, `request timed out after 60000ms`, `failed; trying the next configured provider`.

**Impact:** A real Alexa+ turn has a short timeout, and a 2-minute turn feels broken even in the simulator. Provider instability plus a 60 s × 3 retry budget means a single bad round can consume the whole voice window; the trace then reports success, so the demo looks fine while the user waited two minutes. Multi-round planning and the 27-tool payload multiply both latency and cost.

**Workaround used:** Kept prompts short, retried the turn when the provider failed, and read the trace instead of waiting on the UI.

**Actionable suggestion:**

- Record every attempt in the trace (`provider`, `model`, `attempt`, failure reason) so a green-but-slow turn is explainable in the UI.
- Use a short per-attempt timeout (10–15 s) and a total turn deadline for voice; answer with a spoken fallback instead of stretching to 180 s.
- Route tools by intent instead of exposing all 27 on every turn (read-only planning tools for plan questions, write tools only when a change is requested), or add a compact `study_get_context` aggregate for the common questions.
- Trim tool descriptions/schemas for the model call (keep the full descriptions in MCP for other clients).
- Cap planning rounds at 3–5 and return a partial result instead of exhausting the budget.
- Show elapsed time per turn in the trace panel (tokens are already shown) so regressions are visible.
- Add a smoke test that asserts a plan read completes under a few seconds on a warm server.

---

## F-10 — Documentation drift: broken links, wrong paths, stale behavior notes

**Area:** Documentation / onboarding
**Severity:** Low

**Task attempted:** Follow the repository docs from a clean checkout and navigate between the structure guides.

**Steps taken:**

1. Opened every relative link in `system/STRUCTURE.md`, `system/STRUCTURE_BACKEND.md`, and `system/STRUCTURE_FRONTEND.md`.
2. Followed `app/README.md` steps 3–8.
3. Compared `app/mcp_server/.env.example` with the files it names.
4. Compared the frontend fallback description with `alexa-transport.ts`.
5. Tried `/connectors` and `/connecters`.

**Expected:** Links resolve, commands match the tree, and behavior notes match the code.

**Actual:**

- `system/STRUCTURE.md:16`, `STRUCTURE_BACKEND.md:3,7,127`, and `STRUCTURE_FRONTEND.md:3,86` link to `Others/Acadra - Amazon Hackathon/Project/system/...`. There is no `system/Others` directory; the documents are directly in `system/`.
- `app/mcp_server/.env.example:35` says `db/db_init.py`; the file is `db/init_db.py`.
- `app/README.md:78` says `cd acadra_ai_student_assistant\web`; the web app is `app/web` in this checkout, and step 3 already changed into `mcp_server`.
- `app/web/.env.example:13` sets `MCP_SERVER_URL=http://127.0.0.1:8000/mcp`, while the comment above it says the default is `8001` and `lib/mcp-client.ts:28` defaults to `8001`. Both work with `uv run dev`, but only `8001` works with `uv run api-server`.
- `STRUCTURE_FRONTEND.md:82` says the simulator falls back to “scripted replies”; `app/web/app/alexa+_simulator/alexa-transport.ts:19-24` returns a short apology and explicitly has no scripted domain answers.
- `/connectors` → `404`; `/connecters` → `200`. The misspelling is consistent across the sidebar and docs.
- `app/README.md:19` links to `FRICTION_LOG.md`; that file did not exist before this log (now resolved).

**Evidence:**

- Broken links enumerated above; `Test-Path system/Others` → `False`.
- `app/README.md:40-45,78`; `app/mcp_server/.env.example:35`.
- `app/web/.env.example:5-13`; `app/web/lib/mcp-client.ts:28`.
- `system/STRUCTURE_FRONTEND.md`; `app/web/app/alexa+_simulator/alexa-transport.ts`.

**Impact:** Each item is small; together they cost a new contributor 10–20 minutes of guessing, and the broken structure links make the main navigation between backend/frontend docs fail exactly when someone needs it.

**Workaround used:** Read `system/` directly and used `uv run dev` with `MCP_SERVER_URL` on 8000.

**Actionable suggestion:**

- Fix the `Others/...` links to sibling paths in `system/`.
- Correct `db_init.py` → `init_db.py` and the `app/README.md` web path.
- Pick one canonical backend command (`uv run dev`) and make the sample `MCP_SERVER_URL` match it; mention the `api-server` alternative explicitly.
- Rename the route to `/connectors` with a permanent redirect from `/connecters`, or accept the spelling and remove “Connectors” from copy.
- Add a link-check step (or a small test) for Markdown files in CI.

---

## F-11 — “Today” depends on which process asks, and Upcoming has no timezone input

**Area:** Time handling / API consistency
**Severity:** Low

**Task attempted:** Confirm that the API and the Alexa bridge agree on what day “today” is.

**Steps taken:**

1. Read `get_today_plan` and `get_upcoming_plan`.
2. Read `currentDateLine()` in the bridge.
3. Read the plan routes and preferences schema.

**Verification:** code path; every process ran in the same timezone here, so the mismatch was not triggered.

**Expected:** One student timezone drives “today”, “tonight”, and “tomorrow” everywhere.

**Actual:**

- `get_today_plan(day=None, timezone_name=None)` accepts a timezone and otherwise uses the backend host’s local date (`src/services/tasks.py:546-556`).
- `get_upcoming_plan(days, start_day=None)` has no timezone parameter and also uses the host date (`:569-573`).
- The bridge builds “Today is …” from the Next.js server’s local clock (`app/web/lib/mcp-client.ts:720-739`).
- There is no student timezone in preferences or configuration. If the backend, the Next.js server, and the student are in different zones, the API and the assistant can disagree by a day; so can two deployments.
- `study_get_today_plan` exposes `timezone` to the model, but the model had no reason to pass it, and `study_get_upcoming_plan` cannot.

**Evidence:**

- `app/mcp_server/src/services/tasks.py:546-573`.
- `app/web/lib/mcp-client.ts:720-739`.
- `app/mcp_server/src/db/schema.py:250-256` (`planning_preferences` has no timezone).

**Impact:** Low in a single-machine demo, but the failure is silent and looks like a data bug (“my task disappeared”). A student travelling or a server running in UTC will see the wrong day.

**Workaround used:** Kept every process on the same machine and passed explicit `day` values when testing.

**Actionable suggestion:**

- Add `timezone` to planning preferences (default `UTC` or the account’s zone) and a single resolver used by all plan services and the bridge prompt.
- Add `timezone`/`day` to the upcoming and backlog responses so clients can label them.
- Include the resolved timezone in `study_get_today_plan` and `study_get_upcoming_plan` responses.

---

## F-12 — Debug mode leaks into tests, and a PowerShell pipe makes a passing run look failed

**Area:** Developer experience
**Severity:** Low

**Task attempted:** Run the backend integration suite and read the result.

**Steps taken:**

1. Ran `uv run python -m unittest tests.test_mcp_server`.
2. Ran it again with `2>$null` and checked `$LASTEXITCODE`.
3. Read `src/server.py` and `src/config.py`.

**Expected:** A clean pass/fail result.

**Actual:**

- The suite passes: `Ran 10 tests in 25.610s / OK`, exit code `0` when stderr is suppressed.
- The run emits pages of asyncio debug logs (`Executing <Task …> took 0.7 seconds`, `_ProactorReadPipeTransport._loop_reading`) because the local `.env` sets `STUDY_MCP_DEBUG=True`, and `src/server.py:22` passes it to `FastMCP(..., debug=settings.debug)`.
- Piping with `2>&1 | Select-Object` (a natural PowerShell move) makes PowerShell report exit code `1` and a `NativeCommandError` even though the tests passed.
- `Settings.from_env` defaults `debug` to `"True"` when the variable is unset (`src/config.py:24`), while the Pydantic model default is `False` (`:15`). A checkout without `.env` therefore runs in debug mode, including `reload=True` for uvicorn.

**Evidence:**

- Test output and exit codes above.
- `app/mcp_server/src/server.py:21-22`; `src/config.py:15,24`; `app/mcp_server/.env` (local, not committed).

**Impact:** A developer sees “Exited with code 1” after a green test run and starts debugging the wrong thing. Debug logging also makes CI output unreadable.

**Workaround used:** Re-ran with stderr suppressed and checked `$LASTEXITCODE`; the tests are healthy.

**Actionable suggestion:**

- Do not enable FastMCP/asyncio debug in tests: read debug settings lazily in `main()`, or set `STUDY_MCP_DEBUG=False` in the test command/environment.
- Make the default consistent: `Settings.from_env` should default to `False`, matching the model and `.env.example`.
- Document the Windows/PowerShell invocation (`cmd /c "uv run python -m unittest …"` or check `$LASTEXITCODE`) in the README.
- Optionally add a `uv run test` script that sets the right environment and prints a single summary.

---

## What worked well

The review was not only negative. These parts were stable and worth keeping:

- **Integration tests:** all 10 backend tests passed in 25.6 s against PostgreSQL.
- **REST validation:** `POST /api/academic-items` with a naive datetime returned a precise error (`due_at: Input should have timezone info`) instead of storing a wrong instant.
- **Extraction speed and evidence:** a manual source processed in 19.9 s; the item kept a source revision, evidence quotes, `grade_weight_percent: 20`, `late_penalty: "10% per day"`, and review reasons. The extraction pipeline’s safety design is visible and inspectable.
- **Review visibility:** the item page shows the review reason (`due_at: source evidence is missing`) and the source evidence, so the student can see *why* a record is uncertain — the page even shows the contradiction that F-01 describes.
- **Alexa bridge truthfulness:** the assistant flagged the test item as “still marked as uncertain”, made no unsupported writes, and every write in the trace matched a real tool call. The claim verifier and capability-boundary prompt are doing their job.
- **MCP surface:** 27 `study_*` tools were discovered; the bridge connected over Streamable HTTP on the first attempt and finished planning turns end to end.
- **CRUD that works:** creating, updating, moving, completing, and deleting tasks works; deleting an academic item keeps its tasks and unlinks them; the web Today/Upcoming/Backlog/Inbox/Courses pages render real data.
- **Data hygiene:** test rows could be removed deterministically; after cleanup the counts matched the pre-review snapshot exactly.

## Recommended fix order

| Order | Fix | Why first |
| --- | --- | --- |
| 1 | F-01 + F-11 | Every planning job depends on a stored deadline; fix the validator and give it one timezone. |
| 2 | F-02 | The landing page currently tells a student with 24 open tasks that the day is free. |
| 3 | F-03 | The headline “since I last checked” job is cheap to fix with one cursor and one default. |
| 4 | F-04 + F-05 + F-06 | Build one deterministic planning layer that returns remaining effort, priority with reasons, and a budgeted plan. |
| 5 | F-07 + F-08 | Source management and provider configuration are both about making the system explainable and operable. |
| 6 | F-09 + F-10 + F-12 | Latency, docs, and dev-experience polish before the next demo. |

## Not tested / limits

- **Gmail:** no live Google OAuth, no mailbox import, no retry/expiry behavior. Findings rely on code inspection.
- **File ingestion:** HTML/PDF upload limits and the PDF worker were not exercised this session.
- **Deployment:** no Vercel deploy; serverless transport settings and the ephemeral upload path were not verified.
- **Real Alexa+ hardware/client:** only the local simulator and `POST /api/alexa-chat` were used.
- **UI rendering:** server-rendered HTML was inspected; the desktop was not available for screenshots. Interactive flows (dialogs, drag reorder) were tested through their APIs and code paths, not by clicking.
- **LLM variance:** answers for F-03, F-05, and F-06 are single runs. The structural causes (no cursor, no scoring service, no budget check) are code-level and do not depend on the model’s wording.

## Cleanup

The review created one manual source, one academic item, one change event, and moved one task to test completed-work totals. Cleanup:

- Deleted the test source, its revision, candidate links, processing run, academic item, and change event.
- Restored the moved task to `selected_day = null`, `list_position = 3`, `status = todo`.
- Verified the database returned to the pre-review counts: 13 academic items, 15 changes, 4 source documents, 4 source revisions, 21 source-item links, 4 processing runs, 26 tasks.

The backend integration suite manages its own rows; it may refresh the single `planning_preferences` row. Its stored values (`150`, `4`) were unchanged.

No API keys, OAuth tokens, database URLs, email addresses, or student source contents are reproduced in this log.

## Appendix — raw command evidence

```text
$ uv run python -m unittest tests.test_mcp_server
Ran 10 tests in 25.610s
OK
(exit code 0; stderr suppressed for the clean run)
```

```text
POST /api/sources/text  (19.9 s)
{
  "processing_status": "processed",
  "academic_item_ids": ["ec0273eb-…"],
  "review_count": 1
}

GET /api/academic-items/ec0273eb-…
{
  "item_type": "assignment",
  "due_at": null,
  "grade_weight_percent": "20.0",
  "late_penalty": "10% per day",
  "review_state": "uncertain"
}

GET /api/sources/{id}/candidates
"due_at": {"value": "2026-10-30T23:59", "precision": "datetime", "wording": "2026-10-30T23:59"}
"review_reasons": ["due_at: source evidence is missing"]
```

```text
normalize_candidate() isolation:
literal, no timezone  -> due_at=None, ["due_at: time zone is not in source evidence"]
literal + UTC         -> due_at=2026-10-30 23:59:00+00:00, []
normalized ISO value  -> due_at=None, ["due_at: source evidence is missing"]
```

```text
GET /api/plan/today
{"day":"2026-10-26","total_estimated_minutes":0,"tasks":[]}

GET /api/plan/upcoming?days=7
2026-10-26: 0 tasks, 0m
2026-10-27: 0 tasks, 0m
… all seven days 0m

GET /api/tasks?limit=100
26 tasks, all todo; 24 scheduled 2026-10-19 … 2026-10-25; 2 in Backlog.

GET /api/plan/overdue -> 404
```

```text
PATCH /api/tasks/{id} {"status":"done"}
GET /api/plan/upcoming?days=7 -> 2026-10-27: 1 task, 60m, status=done
PATCH /api/tasks/{id} {"status":"todo"}   (reverted)
```

```text
POST /api/alexa-chat  ("What changed since I last checked?")
tools: study_get_changes_since {"since":"2026-10-26"}, study_list_academic_items {"limit":20}
reply: "Since you last checked, one new item appeared: Assignment 2 …"
GET /api/changes?limit=24 -> 15 events (2026-10-22, 2026-10-23)
```

```text
POST /api/alexa-chat  ("Which assignment is actually the most urgent right now, and why?")
tools: study_list_academic_items {"item_type":"assignment","limit":50}
reply: "The most urgent one is 'Programming assignments' … Everything else either has no due date yet …"
elapsed 24.7 s, 16,075 tokens
```

```text
POST /api/alexa-chat  ("I have 45 minutes before my next class. What should I study?")
reply suggests 30 + 30 + 15 = 75 minutes
elapsed 115.7 s (cold), 12,533 tokens
```

```text
GET /api/sources                          -> 404
GET /api/sources/{id}                     -> 404
DELETE /api/sources/{id}                  -> 404
GET /api/plan/overdue                     -> 404
GET /connectors                           -> 404
GET /connecters                           -> 200
```
