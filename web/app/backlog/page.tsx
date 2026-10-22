import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { TaskGroup } from "@/components/task-group";
import { TaskCreateButton } from "@/components/task-create";
import { backendUnavailableMessage, getBacklog } from "@/lib/tasks";

export const metadata: Metadata = {
  title: "Backlog",
};

export default async function BacklogPage() {
  let backlog = null;
  let error: string | null = null;
  try {
    backlog = await getBacklog(50);
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  const tasks = backlog?.tasks ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Backlog"
        description="Unfinished tasks that have no selected day.">
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
            Backlog is empty. Unscheduled work lands here so you can pick a day
            for it later.
          </p>
          <div className="page-actions"></div>
        </section>
      ) : (
        <section className="panel" aria-labelledby="backlog-list">
          <p className="panel-note" id="backlog-list">
            {tasks.length} {tasks.length === 1 ? "task" : "tasks"} ·{" "}
            <span className="tnum">
              {backlog?.total_estimated_minutes ?? 0} min
            </span>{" "}
            remaining
            {backlog?.has_more ? " · showing the first page" : ""}
          </p>
          <TaskGroup tasks={tasks} />
        </section>
      )}
    </div>
  );
}
