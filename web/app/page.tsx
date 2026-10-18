import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { TaskGroup } from "@/components/task-group";
import { TaskCreateButton } from "@/components/task-create";
import { backendUnavailableMessage, getTodayPlan } from "@/lib/tasks";

export const metadata: Metadata = {
  title: "Today",
};

// Details are clamped on Today so the list stays scannable; the task detail
// page shows the full text.
const TODAY_DETAILS_LINES = 3;

export default async function TodayPage() {
  let plan = null;
  let error: string | null = null;
  try {
    plan = await getTodayPlan();
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  const tasks = plan?.tasks ?? [];
  const total = plan?.total_estimated_minutes ?? 0;
  const defaultDay =
    plan?.day ??
    `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(
      2,
      "0",
    )}-${String(new Date().getDate()).padStart(2, "0")}`;

  return (
    <div className="page">
      <PageHeader
        title="Today"
        description="Your short list for the day. Every step names the action and how long it takes.">
        <TaskCreateButton defaultDay={defaultDay} />
      </PageHeader>

      <dl className="stat-row">
        <div className="stat">
          <dt>Steps today</dt>
          <dd className="tnum">{tasks.length}</dd>
        </div>
        <div className="stat">
          <dt>Estimated effort</dt>
          <dd className="tnum">{total} min</dd>
        </div>
      </dl>

      {error ? (
        <section className="panel">
          <h2>Could not load today&apos;s plan</h2>
          <p className="message error" role="alert">
            {error}
          </p>
        </section>
      ) : tasks.length === 0 ? (
        <section className="panel empty">
          <h2>Nothing is planned for today yet</h2>
          <p className="panel-note">
            Add a course source or create a task. Acadra explains what changed
            in each source and turns it into a step you can start, then places
            that step here.
          </p>
          <div
            className="page-actions"
            style={{ width: "fit-content", margin: "auto" }}>
            <Link className="submit-button" href="/sources/new">
              Add a source
            </Link>
          </div>
        </section>
      ) : (
        <TaskGroup
          tasks={tasks}
          detailsLines={TODAY_DETAILS_LINES}
          showDay={false}
        />
      )}
    </div>
  );
}
