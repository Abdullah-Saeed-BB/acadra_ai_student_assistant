# Acadra Web

Next.js (App Router) student-facing frontend for Acadra. Server components fetch academic data, tasks, and planning preferences through a REST boundary proxied to the Python backend; `/api/alexa-chat` bridges to the study planner's MCP server over Streamable HTTP, discovering and calling `study_*` tools server-side so the browser never reaches the MCP endpoint.

```text
app/web/
├── app/
│   ├── api/
│   │   ├── alexa-chat/route.ts     # Alexa+ chat bridge: validates the conversation and answers through the MCP client
│   │   ├── manual-entry/route.ts   # Proxies manual submissions to the Python API
│   │   ├── gmail-connection/route.ts # Proxies Gmail settings reads and writes
│   │   ├── preferences/route.ts      # Proxies planning preferences reads and writes
│   │   ├── gmail-connection/connect/route.ts # Starts backend OAuth navigation
│   │   ├── tasks/route.ts          # Proxies task creation to the Python API
│   │   ├── tasks/reorder/route.ts  # Proxies drag-order saves for one day's task list
│   │   ├── tasks/[task_id]/route.ts # Proxies task edits (PATCH) to the Python API
│   │   ├── task-options/route.ts   # Aggregates academic items and courses for the task dialog
│   │   ├── academic-items/route.ts # Proxies manual academic item creation to the Python API
│   │   ├── academic-items/[item_id]/route.ts # Proxies academic item edits (PATCH) and deletes
│   │   ├── courses/route.ts        # Proxies course creation to the Python API
│   │   └── courses/[course_id]/route.ts # Proxies course edits (PATCH) and deletes
│   ├── alexa+_simulator/
│   │   ├── page.tsx                # Alexa+ simulator page header and metadata
│   │   ├── alexa-simulator.tsx     # Client chat interface with send, thinking, and scripted replies
│   │   └── alexa-transport.ts      # Chat types; posts to the bridge with scripted-reply fallback
│   ├── backlog/
│   │   └── page.tsx                # Backlog view backed by GET /api/plan/backlog
│   ├── courses/
│   │   └── page.tsx                # Course board: create, edit, and delete courses and their items
│   ├── connecters/
│   │   ├── page.tsx                # Connectors hub: lists available connectors as cards
│   │   └── gmail/
│   │       ├── page.tsx            # Gmail connector page header and metadata
│   │       └── gmail-connection-form.tsx # Client sender-allowlist and OAuth form
│   ├── inbox/
│   │   └── page.tsx                # Inbox: recent academic items and their change feed
│   ├── items/
│   │   └── [item_id]/
│   │       ├── page.tsx            # Academic item detail: fields, source evidence, edit and delete
│   │       └── not-found.tsx       # Missing-item message for the detail view
│   ├── page.tsx                    # Today view: task containers with steps nested in their parent, backed by GET /api/plan/today
│   ├── settings/
│   │   ├── page.tsx                # Settings page
│   │   └── settings-form.tsx       # Client form for planning preferences
│   ├── sources/
│   │   ├── new/
│   │   │   ├── page.tsx            # Add source page header and metadata
│   │   │   └── source-entry-form.tsx # Client manual text and HTML/PDF entry form
│   │   └── [source_document_id]/
│   │       └── page.tsx            # Source detail placeholder
│   ├── tasks/
│   │   ├── page.tsx                # All tasks view: task containers with steps nested in their parent, backed by GET /api/tasks
│   │   └── [task_id]/
│   │       ├── page.tsx            # Top-level task detail view: large task container plus its step containers, backed by GET /api/tasks/{task_id}
│   │       └── not-found.tsx       # Missing-task message for the detail view
│   ├── upcoming/
│   │   └── page.tsx                # Upcoming view: day groups of task containers with steps nested in their parent, backed by GET /api/plan/upcoming
│   ├── layout.tsx                  # Root layout: fonts, metadata, sidebar shell
│   └── globals.css                 # Acadra design tokens and workspace styling
├── lib/
│   ├── academics.ts                # Server-side course, academic item, and change fetchers and types
│   ├── format.ts                   # Calendar-day label formatter shared by the task views
│   ├── mcp-client.ts               # Server-side MCP client bridging the web app to the study planner
│   ├── proxy.ts                    # Shared proxy for browser mutations to the backend REST boundary
│   ├── task-options.ts             # Shared academic-item and course option types and loader for the task dialogs
│   └── tasks.ts                    # Server-side task read/write fetchers and response types
├── components/
│   ├── academic-dialogs.tsx        # Client course and academic-item create/edit dialogs and delete confirm
│   ├── collapsible-section.tsx     # Client collapsible panel wrapper with show/hide toggle
│   ├── course-board.tsx            # Course containers with their items and CRUD controls
│   ├── task-list.tsx               # Agenda-style task list with check and edit; reorders top-level tasks only
│   ├── task-card.tsx               # Task container card (compact or large) with check and edit controls
│   ├── task-group.tsx              # Container list that nests steps and can reorder a parent's steps on demand
│   ├── task-actions.tsx            # Check button, edit dialog, drag handle, and failure notice for tasks
│   ├── use-task-reorder.ts         # Drag-and-drop reorder hook that saves through /api/tasks/reorder
│   ├── task-create.tsx             # "New task"/"Add step" button and dialog for creating a task or sub-task
│   ├── acadra-mark.tsx             # Temporary waypoint mark and acadra lockup
│   ├── app-shell.tsx               # Sidebar plus content frame
│   ├── planned-view.tsx            # Branded placeholder for unbuilt routes
│   ├── page-header.tsx             # Standard page header with display-accent title
│   ├── temp-agent-trace.tsx        # TEMP debug: collapsible LLM thoughts, tool calls/outputs, and full error logs
│   └── sidebar.tsx                 # Primary navigation with active-state waypoints
├── public/                         # Default static assets
├── .env.example                    # Optional backend API and MCP endpoint URLs
├── .gitignore                      # Local build and environment exclusions
├── AGENTS.md                       # Next.js project instructions
├── CLAUDE.md                       # Project guidance pointer
├── DESIGN.md                       # Target Acadra brand and frontend design system
├── eslint.config.mjs               # Lint configuration
├── next.config.ts                  # Next.js configuration
├── package.json                    # Dependencies and scripts
├── package-lock.json               # Locked npm dependencies
├── postcss.config.mjs              # PostCSS configuration
├── README.md                       # Frontend setup notes
└── tsconfig.json                   # TypeScript configuration
```