import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { TaskList } from "@/components/task-list";
import { TaskCreateButton } from "@/components/task-create";
import { backendUnavailableMessage, listTasks } from "@/lib/tasks";

export const metadata: Metadata = {
  title: "All tasks",
};

const ALLOWED_STATUSES = new Set(["todo", "in_progress", "done"]);

export default async function TasksPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; tag?: string }>;
}) {
  const query = await searchParams;
  const params = new URLSearchParams();
  if (query.status && ALLOWED_STATUSES.has(query.status))
    params.set("status", query.status);
  if (query.tag) params.set("tag", query.tag);
  params.set("limit", "50");

  let page = null;
  let error: string | null = null;
  try {
    page = await listTasks(params.toString());
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  const tasks = page?.items ?? [];

  return (
    <div className="page">
      <PageHeader
        title="All tasks"
        description="Every task, with filters for status, course, academic item, and tag.">
        <TaskCreateButton />
      </PageHeader>

      {error ? (
        <section className="panel">
          <p className="message error" role="alert">
            {error}
          </p>
          <div className="page-actions">
            <Link className="connect-button" href="/">
              Back to Today
            </Link>
          </div>
        </section>
      ) : tasks.length === 0 ? (
        <section className="panel empty">
          <p className="panel-note">
            No tasks match{query.status ? ` status “${query.status}”` : ""}.
            Create the first task to start planning.
          </p>
          <div className="page-actions"></div>
        </section>
      ) : (
        <section className="panel" aria-labelledby="tasks-list">
          <p className="panel-note" id="tasks-list">
            {tasks.length} {tasks.length === 1 ? "task" : "tasks"}
            {query.status ? ` · status “${query.status}”` : ""}
            {query.tag ? ` · tag “${query.tag}”` : ""}
            {page?.has_more ? " · showing the first page" : ""}
          </p>
          <TaskList tasks={tasks} />
        </section>
      )}
    </div>
  );
}
