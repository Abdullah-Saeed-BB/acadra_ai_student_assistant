import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { TaskList } from "@/components/task-list";
import { backendUnavailableMessage, getUpcomingPlan } from "@/lib/tasks";

export const metadata: Metadata = {
  title: "Upcoming",
};

export default async function UpcomingPage() {
  let upcoming = null;
  let error: string | null = null;
  try {
    upcoming = await getUpcomingPlan(7);
  } catch (cause) {
    error =
      cause instanceof Error ? cause.message : backendUnavailableMessage();
  }

  return (
    <div className="page">
      <PageHeader
        title="Upcoming"
        description="Tasks selected for the next days, grouped by day."
      />

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
      ) : upcoming &&
        upcoming.days.every((group) => group.tasks.length === 0) ? (
        <section className="panel">
          <p className="panel-note">
            Nothing is scheduled for {upcoming.start_day} to {upcoming.end_day}{" "}
            yet. Choose a day for a backlog task to place it here.
          </p>
          <div className="page-actions">
            <Link className="connect-button" href="/backlog">
              Review backlog
            </Link>
            <Link className="page-link" href="/tasks/new">
              New task
            </Link>
          </div>
        </section>
      ) : (
        <div className="upcoming-tasks">
          {upcoming?.days.map((group) => (
            <section
              key={group.day}
              className="panel"
              aria-labelledby={`day-${group.day}`}>
              <p className="panel-note">
                <span id={`day-${group.day}`}>
                  {group.day} · {group.tasks.length}{" "}
                  {group.tasks.length === 1 ? "task" : "tasks"} ·{" "}
                  <span className="tnum">
                    {group.total_estimated_minutes} min
                  </span>
                </span>
              </p>
              {group.tasks.length > 0 ? (
                <TaskList tasks={group.tasks} />
              ) : (
                <p className="panel-note">No tasks selected for this day.</p>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
